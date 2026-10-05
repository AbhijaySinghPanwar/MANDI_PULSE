"""Methodology: sources, cleaning, assumptions, model results, limitations."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402
from data import UNIT, page_setup, read_csv, read_json, settings  # noqa: E402

from mandipulse.serving import repo_path  # noqa: E402

page_setup("Methodology", icon="📘")
cfg = settings()

st.header("Data")
st.markdown(
    f"""
- **Prices:** Kaggle *Daily Market Prices of Commodity India (2001–2026)* (khandelwalmanas), a copy of
  government **Agmarknet** data, licensed under the **Government Open Data License – India (GODL)**.
  Wholesale modal prices in {UNIT}.
- **Scope:** tomato, onion and potato in Maharashtra, Madhya Pradesh, Uttar Pradesh and Gujarat.
  Analysis period 2018-01-01 to 2025-10-31.
- **Planned:** CEDA (Ashoka University) Agri Market Data, to cross-check prices and add arrival
  quantities; the data.gov.in daily feed for fresh prices.
- **Market locations:** OpenStreetMap (Nominatim). About 1 in 4 markets could only be placed at
  their district centre, so their distances are approximate.
"""
)

st.header("How the data was cleaned")
rec = read_csv("reports/tables/phase2/01_reconciliation.csv")
tot = rec.drop(columns=["state", "commodity"]).sum()
st.markdown(
    f"""
- **{int(tot["raw_rows"]):,} raw rows** → {int(tot["dedupe_exact_dup"])} exact duplicates removed →
  **{int(tot["flagged_invalid"]):,} rows flagged invalid** ({tot["flagged_invalid"] / tot["staging_rows"]:.2%}) and
  kept out of the analysis.
- **Market names:** from Nov 2025 the source renamed markets "X" → "X APMC"; both are treated as
  one market. Other similar names were merged **only** if they are in the same district and never
  report on the same day (decided case by case, every decision recorded).
- **Zero min/max prices** are old placeholders and treated as missing; the modal price is kept.
- **Outliers:** a price is flagged only if it is more than 3× away from **both** the market's own
  last 30 days **and** the same-day median of the state's markets. The simpler rule would have
  deleted the real July 2023 tomato spike.
- **Suspect markets:** {int(tot["suspect_low_rows"]):,} rows in 22 market × crop series sit persistently
  far below the state price. They are kept but left out of the main analysis, and will be checked
  against CEDA.
"""
)

st.header("Cost assumptions (Best Mandi)")
sc = pd.DataFrame(cfg["opportunity"]["scenarios"]).T.rename(
    columns={
        "cost_per_qtl_km": "Freight ₹/qtl/km",
        "fixed_cost_per_qtl": "Handling ₹/qtl",
        "fee_pct": "Fees (share of sale)",
    }
)
sc["Fees (share of sale)"] = sc["Fees (share of sale)"].map(lambda v: f"{v:.0%}")
sc.index = sc.index.str.capitalize()
st.dataframe(sc, width="stretch")
st.caption(
    f"Road distance = straight-line distance × {cfg['geo']['road_factor']}. Fees cover commission "
    "and market fees, which vary by state; spoilage on the road is not included. An opportunity "
    f"needs at least ₹{cfg['opportunity']['min_gain_abs']} per quintal and "
    f"{cfg['opportunity']['min_gain_pct']:.0%} more than selling at home."
)

st.header("How good are the models?")
fm = read_json("reports/ml/price_forecast_metrics.json")["walk_forward"]
val = read_json("reports/ml/forecast_validation_metrics.json")
overall = {r["model"]: r["mae_rs_qtl"] for r in fm["overall"]}
st.subheader("7-day price forecast")
st.dataframe(
    pd.DataFrame(
        {
            "Method": [
                "Model (LightGBM)",
                "'Next week = today'",
                "7-day average",
                "Price 7 days ago",
            ],
            "Average error, ₹/qtl": [
                overall["model_p50"],
                overall["baseline_last_value"],
                overall["baseline_ma7"],
                overall["baseline_value_7d_ago"],
            ],
        }
    ),
    hide_index=True,
)
cal = val["calibration"]["test_may_oct_2025"]
st.markdown(
    f"- Test months May–Oct 2025: the model's error is **{fm['mae_improvement_vs_best_baseline_pct']}% lower** "
    "than the best simple rule. Useful, but modest.\n"
    f"- The model setting (median objective) was checked on an earlier window (Nov 2024–Apr 2025) "
    f"before the test months: winner there = **{val['winner_objective']}**.\n"
    f"- Likely range (p10–p90): after calibration it contains **{cal['after']['all']}%** of actual "
    f"prices (target 80%; before calibration {cal['before']['all']}%)."
)

st.subheader("Crash early warning")
cm = read_json("reports/ml/crash_risk_metrics.json")
nf = cm["segments"]["not_yet_falling"]
nfo = cm["segments"]["not_yet_falling_other_months"]
st.markdown(
    f"""
- **Honest headline:** on days when the price had **not yet started falling**, the model's ranking
  quality (PR-AUC) is **{nf["lightgbm"]["pr_auc"]:.2f}** versus **{nf["seasonal_rule"]["pr_auc"]:.2f}**
  for a "same month last years" rule ({nfo["lightgbm"]["pr_auc"]:.2f} vs {nfo["seasonal_rule"]["pr_auc"]:.2f}
  outside December). At the alert threshold, **about {nf["lightgbm"]["precision_pct"]:.0f}% of early
  warnings come true**, on average **{nf["lightgbm"]["avg_lead_days_true_alerts"]:.1f} days** ahead.
- Over *all* days the numbers look much better (PR-AUC {cm["segments"]["all"]["lightgbm"]["pr_auc"]:.2f}),
  but that is flattering: {cm["share_of_crash_labels_already_below_0_9_at_t_pct"]:.0f}% of crashes are
  already under way when they are labelled.
"""
)
weights = repo_path("reports/ml/crash_logistic_weights.csv")
if weights.exists():
    st.markdown(
        "A simple, transparent version of the crash model (logistic regression) is almost as good. "
        "Its strongest signals (standardised weights; + raises the crash risk):"
    )
    st.dataframe(pd.read_csv(weights).head(10), hide_index=True)
    st.caption(
        "Features keep the model's own names, on a log-price scale. For example, `roll_mean_30_rel` "
        "is the 30-day average relative to today's price. `momentum_30` is exactly the same quantity "
        "with the sign flipped, so the regression splits one effect between them. Together they say: "
        "the further today's price is below its 30-day average, the higher the crash risk."
    )

st.header("Limitations")
st.markdown(
    """
- Modal prices are market indicators, not the price a particular farmer receives (quality, grade
  and the commission agent matter).
- Transport costs and fees are estimates with ranges, not quotes.
- Markets do not report every day; small markets report irregularly.
- Forecasts cannot foresee shocks (weather, export bans, sudden arrivals).
- Data is as of the date in the banner; prices may have changed since.
"""
)
