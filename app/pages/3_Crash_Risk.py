"""Crash Risk: prices falling now (rule) and early warnings (model) for markets not yet falling."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402
from data import (  # noqa: E402
    COMMODITIES,
    UNIT,
    VERIFY_NOTE,
    load,
    page_setup,
    read_json,
    rupees,
    verify_label,
)

FALLING = 0.90  # price below 90% of its 30-day median = falling now
# Diwali 2025: reporting fell from ~650 to ~80-270 markets a day (19-25 Oct, int_analysis_prices)
DIWALI_GAP = (pd.Timestamp("2025-10-19"), pd.Timestamp("2025-10-25"))

page_setup("Crash Risk", icon="⚠️")
st.markdown(
    "A **crash** means the price stays more than 30% below its usual level (the median of the last "
    "30 days) on at least 2 days within the next 2 weeks."
)

status = load("crash_status").merge(
    load("markets")[["market_key", "market", "district", "state"]], on="market_key"
)
n_suspect = int(status["is_suspect_series"].sum())
status = status[~status["is_suspect_series"].astype(bool)]
m = read_json("reports/ml/crash_risk_metrics.json")["segments"]["not_yet_falling"]["lightgbm"]

c1, c2 = st.columns(2)
crop = c1.selectbox("Crop", ["All crops", *COMMODITIES])
states = sorted(status["state"].unique())
state = c2.selectbox("State", ["All states", *states])
s = status.copy()
if crop != "All crops":
    s = s[s["commodity"] == crop]
if state != "All states":
    s = s[s["state"] == state]
s["Market"] = (
    s["needs_verify"].map({True: "⚠️ ", False: ""})
    + s["market"]
    + " ("
    + s["district"]
    + ", "
    + s["state"]
    + ")"
)
s["Latest price"] = s["modal_price"].map(rupees)
s["Usual price (30-day median)"] = s["median_30d"].map(rupees)
s["Last report"] = s["date"].dt.strftime("%d %b %Y")
s["Check"] = s["verify_reason"].map(verify_label)

st.header("1. Falling now")
st.caption(
    f"Simple rule, no model: the latest price is below {FALLING:.0%} of the usual price. {UNIT}."
)
falling = s[s["ratio_to_median"] < FALLING].sort_values("ratio_to_median")
falling = falling.assign(
    **{"Below usual by": (1 - falling["ratio_to_median"]).map(lambda v: f"{v:.0%}")}
)
COLUMNS = [
    "Market",
    "commodity",
    "Latest price",
    "Usual price (30-day median)",
    "Below usual by",
    "Last report",
]
to_verify = falling[falling["needs_verify"].astype(bool)]
confirmed = falling[~falling["needs_verify"].astype(bool)]
if falling.empty:
    st.write("No market is falling right now for this selection.")
else:
    st.markdown(f"**Confirmed ({len(confirmed)})**")
    if confirmed.empty:
        st.write("None for this selection.")
    else:
        st.dataframe(
            confirmed[COLUMNS].rename(columns={"commodity": "Crop"}),
            hide_index=True,
            width="stretch",
        )
if not to_verify.empty:
    single = int(to_verify["verify_reason"].str.startswith("single").sum())
    late_oct = int(
        to_verify["date"].between(DIWALI_GAP[0], DIWALI_GAP[1] + pd.Timedelta(days=14)).sum()
    )
    st.markdown(f"**⚠️ To verify ({len(to_verify)})**")
    note = f"Most of these ({single} of {len(to_verify)}) are a single low report still awaiting a second one"
    if late_oct:
        note += (
            f"; {late_oct} were reported during or just after the late-October (Diwali) reporting "
            "gap, when far fewer markets reported"
        )
    st.caption(note + ".")
    st.dataframe(
        to_verify[[*COLUMNS, "Check"]].rename(columns={"commodity": "Crop"}),
        hide_index=True,
        width="stretch",
    )
    st.caption(VERIFY_NOTE)

st.header("2. Early warning (model)")
st.warning(
    f"**About {m['precision_pct'] / 10:.0f} in 10 early warnings come true, typically "
    f"~{m['avg_lead_days_true_alerts']:.1f} days ahead.** Use this as a prompt to watch prices "
    "closely, not as a certainty.",
    icon="🔔",
)
early = s[(s["ratio_to_median"] >= FALLING) & s["prob"].notna()].copy()
if early.empty:
    st.write("No model scores for this selection.")
else:
    thr = float(early["threshold"].iloc[0])

    def level(p: float) -> str:
        if p >= thr:
            return "High"
        return "Medium" if p >= thr / 2 else "Low"

    early["Risk"] = early["prob"].map(level)
    early["Crash risk"] = early["prob"].map(lambda v: f"{v:.0%}")
    early = early.sort_values("prob", ascending=False)
    counts = early["Risk"].value_counts()
    a, b, c = st.columns(3)
    a.metric("High risk", int(counts.get("High", 0)))
    b.metric("Medium risk", int(counts.get("Medium", 0)))
    c.metric("Low risk", int(counts.get("Low", 0)))
    st.dataframe(
        early[
            [
                "Market",
                "commodity",
                "Risk",
                "Crash risk",
                "Latest price",
                "Usual price (30-day median)",
                "Last report",
            ]
        ].rename(columns={"commodity": "Crop"}),
        hide_index=True,
        width="stretch",
    )
    st.caption(
        f"High = model score at or above the validated alert threshold ({thr:.0%}); Medium = at least "
        "half of it. Crashes are most common in December (harvest arrivals); the model already accounts for the month."
    )
if n_suspect:
    st.caption(
        f"{n_suspect} market × crop series with unreliable prices (persistently far below the state "
        "level; being checked) are left out of both sections."
    )
