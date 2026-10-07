"""Model B: price-crash early warning (spec 9.2, label decision b of 2026-10-04).

Label (int_crash_labels.is_crash): on >= 2 report days within the next 14 days the price is below
70% of its trailing 30-day median. Anchors are REAL report days with a known label.

Evaluation: crashes are strongly seasonal (December), and the spec's May-Oct 2025 test window
contains no December, so Model B uses yearly expanding folds: test years 2022, 2023, 2024 and
Jan-Oct 2025. For test year Y the model trains on anchors whose 14-day horizon ends before Y.
Alert thresholds (target precision >= ml.crash.target_precision) are chosen on the year BEFORE
Y (a model fitted on data before that year), never on the test year itself.

Scores compared on the same rows: prevalence, seasonal rule (training crash rate for
commodity x month), logistic regression, LightGBM (class-weighted).
"""

import json

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from mandipulse.config import get_settings
from mandipulse.ml.data import load_crash_labels
from mandipulse.ml.evaluate import pick_threshold, save_artifacts
from mandipulse.ml.features import (
    CATEGORICAL,
    CRASH_EXTRA_FEATURES,
    FORECAST_FEATURES,
    as_model_frame,
)
from mandipulse.ml.train_forecast import build_frame

CRASH_FEATURES = FORECAST_FEATURES + CRASH_EXTRA_FEATURES
NUMERIC_FEATURES = [c for c in CRASH_FEATURES if c not in CATEGORICAL]
TEST_YEARS = [2022, 2023, 2024, 2025]
MODELS = ["prevalence", "seasonal_rule", "logistic", "lightgbm"]
NOT_YET_FALLING = 0.9  # price at t >= 90% of its trailing 30-day median


def build_crash_frame() -> pd.DataFrame:
    """Model B training frame: features on real report days with crash labels."""
    cfg = get_settings()["ml"]["crash"]
    f = build_frame()
    labels = load_crash_labels()
    f = f.merge(labels, on=["market_key", "commodity_key", "date"], how="inner")  # real report days
    f["anchor_month"] = f["date"].dt.month
    f["lead_days"] = _lead_days(f, cfg["drop_ratio"], cfg["horizon_days"])
    return f


def _lead_days(f: pd.DataFrame, drop_ratio: float, horizon: int) -> pd.Series:
    """Days from t to the first REAL report below drop_ratio x trailing median (for crash rows)."""
    reports = f.set_index(["series_id", "date"])["price_obs"]
    reports = reports[reports.notna()]
    lead = pd.Series(np.nan, index=f.index)
    threshold = drop_ratio * f["lookback_median"].to_numpy()
    for k in range(horizon, 0, -1):  # descending so the smallest k wins
        keys = pd.MultiIndex.from_arrays([f["series_id"], f["date"] + pd.Timedelta(days=k)])
        future = reports.reindex(keys).to_numpy()
        lead[(future < threshold) & (f["is_crash"].to_numpy() == 1)] = k
    return lead


def _seasonal_table(train: pd.DataFrame) -> pd.Series:
    return train.groupby(["commodity", "anchor_month"])["is_crash"].mean()


def _with_hist(df: pd.DataFrame, table: pd.Series, base_rate: float) -> pd.DataFrame:
    keys = pd.MultiIndex.from_arrays([df["commodity"], df["anchor_month"]])
    out = df.copy()
    out["hist_crash_rate"] = table.reindex(keys).fillna(base_rate).to_numpy()
    return out


def _fit_score(train: pd.DataFrame, test: pd.DataFrame, seed: int) -> dict:
    """Scores of every approach on `test`, fitted on `train` only."""
    base = float(train["is_crash"].mean())
    table = _seasonal_table(train)
    tr, te = _with_hist(train, table, base), _with_hist(test, table, base)
    pos = tr["is_crash"].sum()
    clf = lgb.LGBMClassifier(
        n_estimators=400,
        learning_rate=0.05,
        num_leaves=63,
        min_child_samples=100,
        subsample=0.8,
        subsample_freq=1,
        colsample_bytree=0.8,
        scale_pos_weight=(len(tr) - pos) / max(pos, 1),
        random_state=seed,
        deterministic=True,
        force_row_wise=True,
        verbose=-1,
        n_jobs=-1,
    ).fit(as_model_frame(tr, CRASH_FEATURES), tr["is_crash"], categorical_feature=CATEGORICAL)
    medians = tr[NUMERIC_FEATURES].median()
    logit = make_pipeline(
        StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=2000)
    )
    logit.fit(tr[NUMERIC_FEATURES].fillna(medians), tr["is_crash"])
    return {
        "scores": {
            "prevalence": np.full(len(te), base),
            "seasonal_rule": te["hist_crash_rate"].to_numpy(),
            "logistic": logit.predict_proba(te[NUMERIC_FEATURES].fillna(medians))[:, 1],
            "lightgbm": clf.predict_proba(as_model_frame(te, CRASH_FEATURES))[:, 1],
        },
        "lightgbm": clf,
        "logistic": logit,
        "seasonal_table": table,
        "base_rate": base,
    }


def _segment_metrics(df: pd.DataFrame, model: str) -> dict:
    y = df["is_crash"].to_numpy()
    s = df[f"score_{model}"].to_numpy()
    alert = df[f"alert_{model}"].to_numpy()
    tp = int((alert & (y == 1)).sum())
    n_alert = int(alert.sum())
    prevalence = float(y.mean())
    pr_auc = float(average_precision_score(y, s)) if 0 < y.sum() < len(y) else None
    lead = df.loc[alert & (y == 1), "lead_days"].dropna()
    return {
        "n": int(len(y)),
        "n_crash": int(y.sum()),
        "prevalence_pct": round(100 * prevalence, 2),
        "pr_auc": round(pr_auc, 4) if pr_auc is not None else None,
        "lift_over_prevalence": round(pr_auc / prevalence, 2) if pr_auc and prevalence else None,
        "n_alerts": n_alert,
        "precision_pct": round(100 * tp / n_alert, 1) if n_alert else None,
        "recall_pct": round(100 * tp / int(y.sum()), 1) if y.sum() else None,
        "avg_lead_days_true_alerts": round(float(lead.mean()), 1) if len(lead) else None,
    }


def train_crash() -> dict:
    """Model B: yearly walk-forward vs baselines, thresholds, metrics and saved model."""
    cfg = get_settings()["ml"]
    seed, target_precision = cfg["random_seed"], cfg["crash"]["target_precision"]
    horizon = pd.Timedelta(days=cfg["crash"]["horizon_days"])
    f = build_crash_frame()
    print(
        f"  crash frame: {len(f):,} labelled report days, "
        f"prevalence {100 * f['is_crash'].mean():.1f}%"
    )
    results, thresholds = [], {}
    for year in TEST_YEARS:
        start, prev_start = pd.Timestamp(f"{year}-01-01"), pd.Timestamp(f"{year - 1}-01-01")
        test = f[f["date"].dt.year == year]
        train = f[f["date"] + horizon < start]
        # threshold chosen on the previous year with a model that never saw it
        val = f[f["date"].dt.year == year - 1]
        val_fit = _fit_score(f[f["date"] + horizon < prev_start], val, seed)
        thresholds[year] = {}
        for m in MODELS:
            if m == "prevalence":
                thresholds[year][m] = (float("inf"), False)  # a constant score cannot rank alerts
            else:
                thresholds[year][m] = pick_threshold(
                    val["is_crash"].to_numpy(), val_fit["scores"][m], target_precision
                )
        fit = _fit_score(train, test, seed)
        out = test[
            [
                "date",
                "market_key",
                "commodity_key",
                "commodity",
                "state",
                "anchor_month",
                "is_crash",
                "lead_days",
            ]
        ].copy()
        # how far the price at t already sits below its trailing 30-day median
        out["ratio_to_median"] = (test["price_obs"] / test["lookback_median"]).to_numpy()
        out["fold"] = year
        for m in MODELS:
            out[f"score_{m}"] = fit["scores"][m]
            out[f"alert_{m}"] = out[f"score_{m}"] >= thresholds[year][m][0]
        results.append(out)
        print(
            f"  fold {year}: train {len(train):,}, test {len(test):,}, "
            f"lightgbm threshold {thresholds[year]['lightgbm'][0]:.3f}"
        )
    res = pd.concat(results, ignore_index=True)

    # A crash label is "easy" when the fall has already started at t. The honest early-warning test
    # is on days when the price was still >= 90% of its trailing median.
    not_falling = res["ratio_to_median"] >= NOT_YET_FALLING
    segments = {
        "all": res,
        "december": res[res["anchor_month"] == 12],
        "other_months": res[res["anchor_month"] != 12],
        "not_yet_falling": res[not_falling],
        "not_yet_falling_other_months": res[not_falling & (res["anchor_month"] != 12)],
        "already_falling": res[~not_falling],
    }
    metrics = {
        "label": "crash = >= 2 report days in next 14 below 0.7 x trailing 30-day median",
        "test_years": TEST_YEARS,
        "target_precision": target_precision,
        "thresholds": {
            str(y): {
                m: {
                    "threshold": round(t[0], 4) if np.isfinite(t[0]) else None,
                    "reached_target_precision": t[1],
                }
                for m, t in d.items()
            }
            for y, d in thresholds.items()
        },
        "segments": {},
    }
    for seg, df in segments.items():
        metrics["segments"][seg] = {m: _segment_metrics(df, m) for m in MODELS}
        metrics["segments"][seg]["by_commodity"] = {
            c: {m: _segment_metrics(g, m) for m in MODELS} for c, g in df.groupby("commodity")
        }
    metrics["share_of_crash_labels_already_below_0_9_at_t_pct"] = round(
        100 * float((res.loc[res["is_crash"] == 1, "ratio_to_median"] < NOT_YET_FALLING).mean()), 1
    )
    for seg in (
        "all",
        "december",
        "other_months",
        "not_yet_falling",
        "not_yet_falling_other_months",
    ):
        s = metrics["segments"][seg]
        metrics.setdefault("verdict", {})[seg] = {
            "lightgbm_pr_auc": s["lightgbm"]["pr_auc"],
            "seasonal_rule_pr_auc": s["seasonal_rule"]["pr_auc"],
            "logistic_pr_auc": s["logistic"]["pr_auc"],
            "beats_seasonal_rule": bool(s["lightgbm"]["pr_auc"] > s["seasonal_rule"]["pr_auc"]),
            "pr_auc_gain_vs_seasonal_pct": round(
                100
                * (s["lightgbm"]["pr_auc"] - s["seasonal_rule"]["pr_auc"])
                / s["seasonal_rule"]["pr_auc"],
                1,
            ),
        }

    # Final model on all labelled days; alert threshold = the one validated on the last year
    final = _fit_score(f, f.head(1), seed)
    final_threshold = thresholds[TEST_YEARS[-1]]["lightgbm"][0]
    metrics["final_threshold"] = round(final_threshold, 4)
    metrics["n_train_rows_final"] = int(len(f))
    bundle = {
        "model": final["lightgbm"],
        "threshold": final_threshold,
        "seasonal_table": final["seasonal_table"],
        "base_rate": final["base_rate"],
    }
    run_dir = save_artifacts("crash_risk", bundle, metrics, CRASH_FEATURES)
    res.to_parquet(run_dir / "test_predictions.parquet")
    return metrics


if __name__ == "__main__":
    print(json.dumps(train_crash()["verdict"], indent=2))


def logistic_weights() -> pd.DataFrame:
    """Fit the logistic baseline on ALL labelled days and save its standardised coefficients
    (for the app's Methodology page): reports/ml/crash_logistic_weights.csv."""
    from mandipulse.ml.evaluate import REPORT_ML_DIR

    f = build_crash_frame()
    fit = _fit_score(f, f.head(1), get_settings()["ml"]["random_seed"])
    lr = fit["logistic"].named_steps["logisticregression"]
    w = pd.DataFrame({"feature": NUMERIC_FEATURES, "weight": lr.coef_[0]})
    w["abs_weight"] = w["weight"].abs()
    w = w.sort_values("abs_weight", ascending=False).drop(columns="abs_weight").round(4)
    REPORT_ML_DIR.mkdir(parents=True, exist_ok=True)
    w.to_csv(REPORT_ML_DIR / "crash_logistic_weights.csv", index=False)
    return w
