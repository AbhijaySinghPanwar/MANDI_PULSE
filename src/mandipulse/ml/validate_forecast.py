"""Pre-test validation for Model A (Phase 4.1 review fix).

1. Objective choice WITHOUT the test months: walk-forward on Nov 2024 - Apr 2025 (all targets
   before 2025-05-01) comparing the point model fitted with L2 (mean) vs quantile 0.5 (median).
2. Band calibration: conformalised quantile regression (CQR). On the same validation folds,
   score s = max(log p10 - log y, log y - log p90); per commodity, widen the band in log space by
   q_hat = the ceil((n+1) x 0.8)/n quantile of s (target 80% coverage). The widening is applied to
   the saved test-month predictions (May-Oct 2025) to report coverage before / after, and stored
   for scoring (reports/ml/forecast_band_calibration.json).
"""

import json

import lightgbm as lgb
import numpy as np
import pandas as pd

from mandipulse.config import get_settings
from mandipulse.ml.evaluate import REPORT_ML_DIR, coverage, latest_run, regression_metrics
from mandipulse.ml.features import CATEGORICAL, FORECAST_FEATURES, as_model_frame
from mandipulse.ml.train_forecast import BASELINES, build_frame, eligible, lgb_params

VALIDATION_MONTHS = ["2024-11", "2024-12", "2025-01", "2025-02", "2025-03", "2025-04"]
TARGET_COVERAGE = 0.80
CALIBRATION_FILE = REPORT_ML_DIR / "forecast_band_calibration.json"


def _fit(x, y, seed, objective, alpha=None):
    return lgb.LGBMRegressor(**lgb_params(seed, objective, alpha)).fit(
        x, y, categorical_feature=CATEGORICAL
    )


def _cqr_qhat(scores: np.ndarray, target: float) -> float:
    n = len(scores)
    level = min(1.0, np.ceil((n + 1) * target) / n)
    return float(np.quantile(scores, level, method="higher"))


def run_validation() -> dict:
    cfg = get_settings()["ml"]
    seed = cfg["random_seed"]
    f = build_frame()
    has_target = f["target_lp"].notna()
    folds = []
    for month in VALIDATION_MONTHS:
        start = pd.Timestamp(f"{month}-01")
        end = start + pd.offsets.MonthEnd(0)
        ok = eligible(f, start, cfg["min_series_days"])
        train = f[has_target & ok & (f["target_date"] < start)]
        test = f[has_target & ok & (f["target_date"] >= start) & (f["target_date"] <= end)]
        x, y = as_model_frame(train, FORECAST_FEATURES), train["target_lp"] - train["lp_t"]
        xt = as_model_frame(test, FORECAST_FEATURES)
        lp = test["lp_t"].astype(float)
        out = test[
            ["date", "target_date", "commodity", "segment", "target_price", *BASELINES]
        ].copy()
        out["model_l2"] = np.exp(lp + _fit(x, y, seed, "regression").predict(xt))
        out["model_l1"] = np.exp(lp + _fit(x, y, seed, "quantile", 0.5).predict(xt))
        out["q10"] = np.exp(lp + _fit(x, y, seed, "quantile", 0.1).predict(xt))
        out["q90"] = np.exp(lp + _fit(x, y, seed, "quantile", 0.9).predict(xt))
        lo, hi = np.minimum(out["q10"], out["q90"]), np.maximum(out["q10"], out["q90"])
        out["q10"], out["q90"] = lo, hi
        out["fold"] = month
        folds.append(out)
        print(f"  validation fold {month}: train {len(train):,}, test {len(test):,}")
    v = pd.concat(folds, ignore_index=True)

    cols = ["model_l1", "model_l2", *BASELINES]
    overall = {c: regression_metrics(v["target_price"], v[c]) for c in cols}
    by_commodity = {
        com: {c: regression_metrics(g["target_price"], g[c]) for c in cols}
        for com, g in v.groupby("commodity")
    }
    by_fold = {
        m: {c: regression_metrics(g["target_price"], g[c])["mae_rs_qtl"] for c in cols}
        for m, g in v.groupby("fold")
    }
    best_baseline = min(BASELINES, key=lambda b: overall[b]["mae_rs_qtl"])
    winner = (
        "model_l1"
        if overall["model_l1"]["mae_rs_qtl"] <= overall["model_l2"]["mae_rs_qtl"]
        else "model_l2"
    )

    # --- CQR calibration per commodity (log space) ---------------------------------------
    ly = np.log(v["target_price"].astype(float))
    s = np.maximum(np.log(v["q10"]) - ly, ly - np.log(v["q90"]))
    qhat = {
        com: round(_cqr_qhat(s[v["commodity"] == com].to_numpy(), TARGET_COVERAGE), 5)
        for com in sorted(v["commodity"].unique())
    }
    val_cov_before = coverage(v["target_price"], v["q10"], v["q90"])
    w = v["commodity"].map(qhat)
    val_cov_after = coverage(v["target_price"], v["q10"] * np.exp(-w), v["q90"] * np.exp(w))

    metrics = {
        "validation_months": VALIDATION_MONTHS,
        "note": "all validation targets dated before 2025-05-01 (the test window)",
        "n_rows": int(len(v)),
        "overall": overall,
        "by_commodity": by_commodity,
        "mae_by_fold": by_fold,
        "best_baseline": best_baseline,
        "winner_objective": "L1 (median)" if winner == "model_l1" else "L2 (mean)",
        "l1_vs_l2_mae_pct": round(
            100
            * (overall["model_l2"]["mae_rs_qtl"] - overall["model_l1"]["mae_rs_qtl"])
            / overall["model_l2"]["mae_rs_qtl"],
            1,
        ),
        "l1_vs_best_baseline_pct": round(
            100
            * (overall[best_baseline]["mae_rs_qtl"] - overall["model_l1"]["mae_rs_qtl"])
            / overall[best_baseline]["mae_rs_qtl"],
            1,
        ),
        "l2_vs_best_baseline_pct": round(
            100
            * (overall[best_baseline]["mae_rs_qtl"] - overall["model_l2"]["mae_rs_qtl"])
            / overall[best_baseline]["mae_rs_qtl"],
            1,
        ),
        "calibration": {
            "method": "CQR per commodity, log space, target 80%, fitted on validation folds",
            "qhat_log_by_commodity": qhat,
            "validation_coverage_before": val_cov_before,
            "validation_coverage_after": val_cov_after,
            **band_coverage(qhat),
        },
    }
    REPORT_ML_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_ML_DIR / "forecast_validation_metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    CALIBRATION_FILE.write_text(
        json.dumps(
            {"method": metrics["calibration"]["method"], "qhat_log_by_commodity": qhat}, indent=2
        ),
        encoding="utf-8",
    )
    return metrics


def calibrated_band(p10, p50, p90, widen):
    """Widen the band by `widen` (log space) and keep p10 <= p50 <= p90.

    The three quantile models are fitted separately, so on a few rows their outputs cross; the
    band edges are clipped to the median (the median itself is never changed).
    """
    lo = np.minimum(np.asarray(p10, dtype=float) * np.exp(-np.asarray(widen, dtype=float)), p50)
    hi = np.maximum(np.asarray(p90, dtype=float) * np.exp(np.asarray(widen, dtype=float)), p50)
    return lo, hi


def band_coverage(qhat: dict) -> dict:
    """Coverage before / after calibration on the saved test-month and stress-test predictions."""
    run = latest_run("price_forecast")
    test_cov = {}
    for name, file in (
        ("test_may_oct_2025", "walk_forward_predictions.parquet"),
        ("stress_test_jul_aug_2023", "stress_test_predictions.parquet"),
    ):
        p = pd.read_parquet(run / file)
        lo, hi = calibrated_band(
            p["model_p10"], p["model_p50"], p["model_p90"], p["commodity"].map(qhat)
        )
        lo, hi = pd.Series(lo, index=p.index), pd.Series(hi, index=p.index)
        test_cov[name] = {
            "before": {
                "all": coverage(p["target_price"], p["model_p10"], p["model_p90"]),
                **{
                    f"segment_{k}": coverage(g["target_price"], g["model_p10"], g["model_p90"])
                    for k, g in p.groupby("segment")
                },
                **{
                    k: coverage(g["target_price"], g["model_p10"], g["model_p90"])
                    for k, g in p.groupby("commodity")
                },
            },
            "after": {
                "all": coverage(p["target_price"], lo, hi),
                **{
                    f"segment_{k}": coverage(g["target_price"], lo[g.index], hi[g.index])
                    for k, g in p.groupby("segment")
                },
                **{
                    k: coverage(g["target_price"], lo[g.index], hi[g.index])
                    for k, g in p.groupby("commodity")
                },
            },
            "median_band_width_pct_before": round(
                float(100 * ((p["model_p90"] - p["model_p10"]) / p["model_p50"]).median()), 1
            ),
            "median_band_width_pct_after": round(
                float(100 * ((hi - lo) / p["model_p50"]).median()), 1
            ),
        }

    return test_cov


def recalibrate_test_coverage() -> dict:
    """Recompute only the test/stress coverage in the saved metrics (no retraining)."""
    path = REPORT_ML_DIR / "forecast_validation_metrics.json"
    metrics = json.loads(path.read_text(encoding="utf-8"))
    metrics["calibration"].update(band_coverage(metrics["calibration"]["qhat_log_by_commodity"]))
    path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def load_calibration() -> dict:
    if CALIBRATION_FILE.exists():
        return json.loads(CALIBRATION_FILE.read_text(encoding="utf-8"))["qhat_log_by_commodity"]
    return {}
