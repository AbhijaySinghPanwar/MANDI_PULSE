"""Render the tables of reports/ML_REPORT.md from the saved metrics files (reports/ml/*.json).

    python -m mandipulse ml report

Every number in the report's tables comes from these files; the narrative sections live in
reports/ml/ML_REPORT.template.md and reference the tables with {{placeholders}}.
"""

import json
import re

import pandas as pd

from mandipulse.config import PROJECT_ROOT
from mandipulse.ml.evaluate import REPORT_ML_DIR

TEMPLATE = REPORT_ML_DIR / "ML_REPORT.template.md"
OUT = PROJECT_ROOT / "reports" / "ML_REPORT.md"

MODEL_LABELS = {
    "model_p50": "**LightGBM (p50)**",
    "baseline_last_value": "Last value",
    "baseline_value_7d_ago": "Value 7 days ago",
    "baseline_ma7": "7-day moving average",
    "prevalence": "Prevalence (base rate)",
    "seasonal_rule": "Seasonal rule (crop x month)",
    "logistic": "Logistic regression",
    "lightgbm": "**LightGBM**",
}


def _load(name: str) -> dict:
    return json.loads((REPORT_ML_DIR / f"{name}_metrics.json").read_text(encoding="utf-8"))


def _md(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in df.itertuples(index=False):
        cells = [
            "–" if (v is None or (isinstance(v, float) and pd.isna(v))) else str(v) for v in row
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _forecast_table(rows: list[dict], group_label: str | None = None) -> str:
    df = pd.DataFrame(rows)
    df["model"] = df["model"].map(MODEL_LABELS)
    cols = ["model", "n", "mae_rs_qtl", "mape_pct", "smape_pct"]
    if group_label:
        df = df.rename(columns={"group": group_label})
        cols = [group_label, *cols]
    df = df[cols].rename(
        columns={
            "model": "Model",
            "n": "Rows",
            "mae_rs_qtl": "MAE (Rs/qtl)",
            "mape_pct": "MAPE %",
            "smape_pct": "sMAPE %",
        }
    )
    return _md(df)


def _crash_table(seg: dict) -> str:
    rows = []
    for m in ["prevalence", "seasonal_rule", "logistic", "lightgbm"]:
        r = seg[m]
        rows.append(
            {
                "Model": MODEL_LABELS[m],
                "PR-AUC": r["pr_auc"],
                "Lift over prevalence": r["lift_over_prevalence"],
                "Precision %": r["precision_pct"],
                "Recall %": r["recall_pct"],
                "Alerts": r["n_alerts"],
                "Avg lead (days)": r["avg_lead_days_true_alerts"],
            }
        )
    head = (
        f"Rows: {seg['lightgbm']['n']:,}; crash days: {seg['lightgbm']['n_crash']:,} "
        f"(prevalence {seg['lightgbm']['prevalence_pct']}%).\n\n"
    )
    return head + _md(pd.DataFrame(rows))


def blocks() -> dict[str, str]:
    """Every template placeholder -> its rendered text or table."""
    a, b, c = _load("price_forecast"), _load("crash_risk"), _load("market_cluster")
    wf, st = a["walk_forward"], a["stress_test_jul_aug_2023"]
    out = {
        "a_overall": _forecast_table(wf["overall"]),
        "a_by_commodity": _forecast_table(wf["by_commodity"], "Crop"),
        "a_by_segment": _forecast_table(wf["by_segment"], "Segment"),
        "a_by_fold": _md(
            pd.DataFrame(
                [
                    {
                        "Test month": k,
                        "Rows": v["n"],
                        "MAE (Rs/qtl)": v["mae_rs_qtl"],
                        "MAPE %": v["mape_pct"],
                    }
                    for k, v in a["walk_forward_by_fold"].items()
                ]
            )
        ),
        "a_coverage": ", ".join(f"{k} {v}%" for k, v in wf["band_coverage_pct"].items()),
        "a_improvement": f"{wf['mae_improvement_vs_best_baseline_pct']}%",
        "a_best_baseline": MODEL_LABELS[wf["best_baseline"]],
        "a_stress_overall": _forecast_table(st["overall"]),
        "a_stress_tomato": _forecast_table(st["tomato"]),
        "a_stress_coverage": ", ".join(f"{k} {v}%" for k, v in st["band_coverage_pct"].items()),
        "a_stress_improvement": f"{st['mae_improvement_vs_best_baseline_pct']}%",
        "b_all": _crash_table(b["segments"]["all"]),
        "b_december": _crash_table(b["segments"]["december"]),
        "b_other": _crash_table(b["segments"]["other_months"]),
        "b_not_falling": _crash_table(b["segments"]["not_yet_falling"]),
        "b_not_falling_other": _crash_table(b["segments"]["not_yet_falling_other_months"]),
        "b_already_falling_share": f"{b['share_of_crash_labels_already_below_0_9_at_t_pct']}%",
        "b_verdict": _md(
            pd.DataFrame(
                [
                    {
                        "Segment": seg.replace("_", " "),
                        "LightGBM PR-AUC": v["lightgbm_pr_auc"],
                        "Seasonal rule PR-AUC": v["seasonal_rule_pr_auc"],
                        "Logistic PR-AUC": v["logistic_pr_auc"],
                        "Beats seasonal rule?": "yes" if v["beats_seasonal_rule"] else "**no**",
                        "Gain vs seasonal": f"{v['pr_auc_gain_vs_seasonal_pct']}%",
                    }
                    for seg, v in b["verdict"].items()
                ]
            )
        ),
        "b_thresholds": _md(
            pd.DataFrame(
                [
                    {
                        "Test year": y,
                        "LightGBM threshold": v["lightgbm"]["threshold"],
                        "Reached precision >= 0.6 on validation year?": "yes"
                        if v["lightgbm"]["reached_target_precision"]
                        else "no",
                    }
                    for y, v in b["thresholds"].items()
                ]
            )
        ),
        "c_silhouette": ", ".join(f"k={k}: {v}" for k, v in c["silhouette_by_k"].items()),
        "c_k": str(c["chosen_k"]),
        "c_profiles": _md(
            pd.DataFrame(c["cluster_profiles_median"])
            .drop(columns=["cluster_id"])
            .rename(
                columns={
                    "cluster_name": "Cluster",
                    "n_series": "Series",
                    "cv": "CV",
                    "price_index": "Price index",
                    "report_freq": "Report freq",
                    "seasonal_amplitude": "Seasonal amp.",
                    "crash_rate": "Crash rate",
                    "n_markets_within_50km": "Towns ≤50 km",
                    "n_suspect_series": "Suspect-low series",
                }
            )
            .round(3)
        ),
        "c_suspect": ", ".join(f"{k}: {v}" for k, v in c["suspect_series"]["by_cluster"].items()),
        "c_n_suspect": str(c["suspect_series"]["n_in_clustering"]),
    }

    # single values used in the narrative
    def mae(rows, model, group="all"):
        return next(r["mae_rs_qtl"] for r in rows if r["model"] == model and r["group"] == group)

    for crop in ("Onion", "Potato", "Tomato"):
        out[f"a_{crop.lower()}_model"] = str(mae(wf["by_commodity"], "model_p50", crop))
        out[f"a_{crop.lower()}_last"] = str(mae(wf["by_commodity"], "baseline_last_value", crop))
    out["a_mae_model"] = str(mae(wf["overall"], "model_p50"))
    out["a_mae_last"] = str(mae(wf["overall"], "baseline_last_value"))
    for seg in ("frequent", "sparse"):
        out[f"a_{seg}_model"] = str(mae(wf["by_segment"], "model_p50", seg))
        out[f"a_{seg}_last"] = str(mae(wf["by_segment"], "baseline_last_value", seg))
    out["a_stress_tomato_model"] = str(mae(st["tomato"], "model_p50"))
    out["a_stress_tomato_last"] = str(mae(st["tomato"], "baseline_last_value"))
    run1 = json.loads(
        (REPORT_ML_DIR / "attempts" / "price_forecast_metrics_run1_l2_objective.json").read_text(
            encoding="utf-8"
        )
    )
    out["a_run1_improvement"] = f"{run1['walk_forward']['mae_improvement_vs_best_baseline_pct']}%"
    out["a_run1_mae"] = str(mae(run1["walk_forward"]["overall"], "model_p50"))
    seg = b["segments"]
    for key, name in (
        ("nf", "not_yet_falling"),
        ("nfo", "not_yet_falling_other_months"),
        ("dec", "december"),
        ("oth", "other_months"),
        ("all", "all"),
    ):
        for m in ("lightgbm", "seasonal_rule", "logistic"):
            for f in (
                "pr_auc",
                "precision_pct",
                "recall_pct",
                "avg_lead_days_true_alerts",
                "lift_over_prevalence",
            ):
                out[f"b_{key}_{m}_{f}"] = str(seg[name][m][f])
        out[f"b_{key}_prev"] = str(seg[name]["lightgbm"]["prevalence_pct"])
    # ---- Phase 4.1: pre-test validation window + band calibration ----------------------
    vpath = REPORT_ML_DIR / "forecast_validation_metrics.json"
    if vpath.exists():
        v = json.loads(vpath.read_text(encoding="utf-8"))
        labels = {
            "model_l1": "**LightGBM, median (L1) objective**",
            "model_l2": "LightGBM, mean (L2) objective",
            **{
                k: MODEL_LABELS[k]
                for k in ("baseline_last_value", "baseline_value_7d_ago", "baseline_ma7")
            },
        }
        out["v_table"] = _md(
            pd.DataFrame(
                [
                    {
                        "Model": labels[k],
                        "Rows": r["n"],
                        "MAE (Rs/qtl)": r["mae_rs_qtl"],
                        "MAPE %": r["mape_pct"],
                        "sMAPE %": r["smape_pct"],
                    }
                    for k, r in v["overall"].items()
                ]
            )
        )
        out["v_by_fold"] = _md(
            pd.DataFrame(
                [
                    {
                        "Validation month": m,
                        "L1 MAE": r["model_l1"],
                        "L2 MAE": r["model_l2"],
                        "Last value MAE": r["baseline_last_value"],
                    }
                    for m, r in v["mae_by_fold"].items()
                ]
            )
        )
        out["v_winner"] = v["winner_objective"]
        out["v_l1_vs_l2"] = f"{v['l1_vs_l2_mae_pct']}%"
        out["v_l1_vs_base"] = f"{v['l1_vs_best_baseline_pct']}%"
        out["v_l2_vs_base"] = f"{v['l2_vs_best_baseline_pct']}%"
        l1_wins = v["winner_objective"].startswith("L1")
        out["v_verdict"] = (
            "**The median (L1) objective also wins on the pre-test validation window, so the choice is "
            "justified without using the test months.**"
            if l1_wins
            else "**On the pre-test validation window the mean (L2) objective wins.** Following the rule agreed "
            "for this check, the served model should use the L2 objective; see 'Decisions'."
        )
        cal = v["calibration"]
        out["cal_qhat"] = ", ".join(
            f"{k} {val:.3f}" for k, val in cal["qhat_log_by_commodity"].items()
        )
        rows = []
        for window, label in (
            ("test_may_oct_2025", "Test months May-Oct 2025"),
            ("stress_test_jul_aug_2023", "Stress test Jul-Aug 2023"),
        ):
            for key in cal[window]["before"]:
                rows.append(
                    {
                        "Window": label,
                        "Slice": key.replace("segment_", "segment: "),
                        "Coverage before %": cal[window]["before"][key],
                        "Coverage after %": cal[window]["after"][key],
                    }
                )
        out["cal_table"] = _md(pd.DataFrame(rows))
        out["cal_val_before"] = str(cal["validation_coverage_before"])
        out["cal_val_after"] = str(cal["validation_coverage_after"])
        out["cal_width_before"] = str(cal["test_may_oct_2025"]["median_band_width_pct_before"])
        out["cal_width_after"] = str(cal["test_may_oct_2025"]["median_band_width_pct_after"])
        out["cal_test_before"] = str(cal["test_may_oct_2025"]["before"]["all"])
        out["cal_test_after"] = str(cal["test_may_oct_2025"]["after"]["all"])
    out["b_share_falling"] = str(b["share_of_crash_labels_already_below_0_9_at_t_pct"])
    for name in ("price_forecast", "crash_risk"):
        path = REPORT_ML_DIR / f"shap_{name}.json"
        if path.exists():
            rank = json.loads(path.read_text(encoding="utf-8"))[:10]
            out[f"shap_{name}"] = _md(
                pd.DataFrame(
                    [
                        {
                            "Rank": i + 1,
                            "Feature": r["feature"],
                            "Mean abs SHAP": r["mean_abs_shap"],
                            "Direction (corr. of value with SHAP)": r["corr_value_vs_shap"],
                        }
                        for i, r in enumerate(rank)
                    ]
                )
            )
    return out


def render() -> str:
    """Render reports/ML_REPORT.md from the template and saved metrics."""
    t = TEMPLATE.read_text(encoding="utf-8")
    b = blocks()
    missing = sorted(set(re.findall(r"\{\{(\w+)\}\}", t)) - set(b))
    if missing:
        raise KeyError(f"template placeholders without data: {missing}")
    out = re.sub(r"\{\{(\w+)\}\}", lambda m: b[m.group(1)], t)
    OUT.write_text(out, encoding="utf-8", newline="\n")
    return str(OUT)
