"""Price Outlook: recent prices and the 7-day forecast for one market and crop."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import altair as alt  # noqa: E402
import streamlit as st  # noqa: E402
from data import (  # noqa: E402
    COMMODITIES,
    UNIT,
    load,
    market_options,
    page_setup,
    read_json,
    rupees,
)

page_setup("Price Outlook", icon="📈")
st.markdown(
    "Recent prices for one market, what our model forecast **7 days ahead** during the test "
    "months (May–Oct 2025), and its latest forecast. The simple rule *“next week's price = "
    "today's price”* is shown too, so you can judge whether the model adds anything."
)

markets = load("markets")
history = load("price_history")
backtest = load("forecast_backtest")
latest = load("forecast_latest")

c1, c2 = st.columns([1, 2])
crop = c1.selectbox("Crop", COMMODITIES)
with_bt = backtest[backtest["commodity"] == crop]["market_key"].value_counts()
pool = markets[markets["market_key"].isin(with_bt.index)]
if pool.empty:
    st.warning("No forecasts available for this crop yet.")
    st.stop()
options = market_options(pool)
default = list(options).index(with_bt.index[0]) if with_bt.index[0] in options else 0
key = c2.selectbox(
    "Market (State › District › Market)", list(options), index=default, format_func=options.get
)

h = history[(history["market_key"] == key) & (history["commodity"] == crop)]
b = backtest[(backtest["market_key"] == key) & (backtest["commodity"] == crop)]
f = latest[(latest["market_key"] == key) & (latest["commodity"] == crop)]

actual = (
    alt.Chart(h)
    .mark_line(color="#0b0b0b", strokeWidth=1.8)
    .encode(
        x=alt.X("date:T", title=None),
        y=alt.Y("modal_price:Q", title=f"Price, {UNIT}"),
        tooltip=[
            alt.Tooltip("date:T", title="Date"),
            alt.Tooltip("modal_price:Q", title="Actual ₹/qtl", format=",.0f"),
        ],
    )
)
band = (
    alt.Chart(b)
    .mark_area(color="#cde2fb", opacity=0.9)
    .encode(
        x="target_date:T",
        y="p10:Q",
        y2="p90:Q",
        tooltip=[
            alt.Tooltip("target_date:T", title="Date"),
            alt.Tooltip("p10:Q", format=",.0f", title="Low (p10)"),
            alt.Tooltip("p90:Q", format=",.0f", title="High (p90)"),
        ],
    )
)
model = (
    alt.Chart(b)
    .mark_line(color="#2a78d6", strokeWidth=2)
    .encode(
        x="target_date:T",
        y="p50:Q",
        tooltip=[
            alt.Tooltip("target_date:T", title="Date"),
            alt.Tooltip("p50:Q", format=",.0f", title="Model forecast"),
        ],
    )
)
baseline = (
    alt.Chart(b)
    .mark_line(color="#eb6834", strokeWidth=1.4, strokeDash=[4, 3])
    .encode(
        x="target_date:T",
        y="baseline_last_value:Q",
        tooltip=[
            alt.Tooltip("target_date:T", title="Date"),
            alt.Tooltip("baseline_last_value:Q", format=",.0f", title="'Same as today' rule"),
        ],
    )
)
layers = [band, actual, model, baseline]
if not f.empty:
    point = (
        alt.Chart(f)
        .mark_point(color="#2a78d6", filled=True, size=90)
        .encode(
            x="horizon_date:T",
            y="p50:Q",
            tooltip=[
                alt.Tooltip("horizon_date:T", title="Forecast for"),
                alt.Tooltip("p50:Q", format=",.0f", title="Forecast"),
                alt.Tooltip("p10:Q", format=",.0f", title="Low"),
                alt.Tooltip("p90:Q", format=",.0f", title="High"),
            ],
        )
    )
    rule = (
        alt.Chart(f)
        .mark_rule(color="#2a78d6", strokeWidth=2)
        .encode(x="horizon_date:T", y="p10:Q", y2="p90:Q")
    )
    layers += [rule, point]
st.altair_chart(
    alt.layer(*layers).properties(height=380).interactive(bind_y=False), width="stretch"
)
st.caption(
    "Black = actual reported price. Blue = model forecast made 7 days earlier, with its likely range "
    "(shaded, about 8 in 10 prices should fall inside). Orange dashed = 'next week = today' rule. "
    "Blue dot = latest forecast."
)

if not f.empty:
    r = f.iloc[0]
    st.success(
        f"Latest forecast for **{r['horizon_date']:%d %b %Y}**: about **{rupees(r['p50'])}** "
        f"(likely range {rupees(r['p10'])} – {rupees(r['p90'])}), {UNIT}."
    )

metrics = read_json("reports/ml/price_forecast_metrics.json")["walk_forward"]["by_commodity"]
val = read_json("reports/ml/forecast_validation_metrics.json")
mae = {r["model"]: r["mae_rs_qtl"] for r in metrics if r["group"] == crop}
st.subheader(f"How accurate is this for {crop.lower()}?")
k1, k2, k3 = st.columns(3)
k1.metric(
    "Model: average error",
    rupees(mae["model_p50"]),
    help="Mean absolute error, test months May–Oct 2025.",
)
k2.metric("'Same as today' rule: average error", rupees(mae["baseline_last_value"]))
k3.metric(
    "Range contains the actual price",
    f"{val['calibration']['test_may_oct_2025']['after'].get(crop, val['calibration']['test_may_oct_2025']['after']['all'])}%",
    help="Share of test-month prices inside the calibrated p10–p90 range (target 80%).",
)
st.caption(
    "The model is only modestly better than assuming next week's price equals today's. Treat the "
    "forecast as a guide, especially in sudden spikes or crashes, which no price-history model can foresee."
)
