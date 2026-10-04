"""Build notebooks 01-04 (spec section 8) from the cell sources below.

    python notebooks/build_notebooks.py
    python -m ipykernel install --sys-prefix --name mandipulse   (once, inside the venv)
    python -m nbconvert --to notebook --execute --inplace notebooks/0*.ipynb

Every number comes from a saved query in analysis/queries/ via mandipulse.viz.load(), which
also writes the query's CSV to reports/tables/ (the table view of each figure).
"""

from pathlib import Path

import nbformat as nbf

HERE = Path(__file__).parent

SETUP = """\
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import pandas as pd
from mandipulse import viz
from mandipulse.viz import COMMODITIES, COMMODITY_COLORS, INK, INK_2, MUTED, load
pd.set_option("display.width", 160)
viz.style()"""

STATE_COLORS = """\
# States use categorical slots 4-7 of the reference palette in fixed order (validated separately).
STATE_COLORS = {"Gujarat": "#eda100", "Madhya Pradesh": "#e87ba4",
                "Maharashtra": "#008300", "Uttar Pradesh": "#4a3aa7"}"""

NOTEBOOKS = {
    "01_eda.ipynb": [
        (
            "md",
            "# 01 - Exploratory data analysis\n\nCoverage, data quality and price levels of the analysis base "
            "(`marts.int_analysis_prices`: main period 2018-01-01..2025-10-31, valid rows, suspect-low excluded). "
            "All numbers come from saved queries in `analysis/queries/`.",
        ),
        ("code", SETUP),
        ("code", STATE_COLORS),
        ("md", "## Coverage: markets reporting per month"),
        (
            "code",
            """\
cov = load("phase3", "eda_01_markets_reporting_by_month")
cov["month"] = pd.to_datetime(cov["month"])
fig, ax = viz.figure("Markets reporting each month, by state",
                     "Distinct markets with >= 1 valid price (any crop) per month")
for state, g in cov.groupby("state"):
    ax.plot(g["month"], g["n_markets_reporting"], color=STATE_COLORS[state], label=state)
viz.label_line_ends(ax, cov, "month", "n_markets_reporting", "state")
ax.set_ylabel("markets reporting")
ax.set_ylim(0)
viz.legend(ax, ncols=4)
viz.save(fig, "eda_markets_reporting_by_month",
         note="Madhya Pradesh dips in Jan-Sep 2024 (known reporting gap); 2025 thins before the Nov-2025 source change.")
cov.pivot(index="month", columns="state", values="n_markets_reporting").tail(12)""",
        ),
        (
            "code",
            """\
load("phase3", "eda_02_coverage_by_state_crop")""",
        ),
        ("md", "## Data quality: share of rows flagged invalid, by year"),
        (
            "code",
            """\
flags = load("phase2", "02_flag_rates_by_year").dropna(subset=["year"])
flags["year"] = flags["year"].astype(int)
fig, ax = viz.figure("Rows flagged invalid, by year",
                     "% of staging rows failing >= 1 validity flag (order, outlier, unit); suspect-low is not counted")
ax.bar(flags["year"], flags["pct_invalid"], color=viz.SEQUENTIAL[4], width=0.6)
for x, y in zip(flags["year"], flags["pct_invalid"], strict=True):
    ax.annotate(f"{y:.2f}%", (x, y), xytext=(0, 3), textcoords="offset points", ha="center",
                fontsize=8.5, color=INK_2)
ax.set_ylabel("% of rows invalid")
ax.set_xticks(flags["year"])
viz.save(fig, "eda_invalid_rate_by_year")
flags[["year", "n_rows", "n_order", "n_outlier", "n_unit_suspect", "n_invalid", "n_suspect_low", "pct_invalid"]]""",
        ),
        ("md", "## Price levels: monthly median modal price"),
        (
            "code",
            """\
px = load("phase3", "eda_03_median_price_monthly")
px["month"] = pd.to_datetime(px["month"])
fig, ax = viz.figure("Monthly median wholesale price by crop",
                     "Median of daily modal prices across all markets, Rs per quintal")
for c in COMMODITIES:
    g = px[px["commodity"] == c]
    ax.plot(g["month"], g["median_modal_rs_qtl"], color=COMMODITY_COLORS[c], label=c)
viz.label_line_ends(ax, px, "month", "median_modal_rs_qtl", "commodity")
ax.set_ylabel("Rs / quintal")
ax.set_ylim(0)
viz.legend(ax)
viz.save(fig, "eda_median_price_monthly",
         note="Tomato spikes (e.g. Jul 2023) and onion spikes (e.g. late 2019, 2020) are visible; prices are not inflation-adjusted.")
px.groupby("commodity")["median_modal_rs_qtl"].describe()""",
        ),
    ],
    "02_spreads_and_opportunities.ipynb": [
        (
            "md",
            "# 02 - Price spreads and net-price opportunities (Q1, Q2)\n\n"
            "Q1: how big is the same-day price gap between nearby mandis (<= 100 km road estimate)?  \n"
            "Q2: after transport costs, how often is selling at a farther mandi profitable, and by how much?",
        ),
        ("code", SETUP),
        ("md", "## Q1 - same-day gap between nearby markets"),
        (
            "code",
            """\
q1 = load("phase3", "q1_spread_by_commodity")
q1""",
        ),
        (
            "code",
            """\
dist = load("phase3", "q1_gap_by_distance")
dist["band_mid"] = dist["road_km_band_start"] + 10
fig, ax = viz.figure("Q1. Same-day price gap between market pairs, by distance",
                     "Median gap as % of the lower price, pairs <= 100 km road estimate, days both reported")
for c in COMMODITIES:
    g = dist[dist["commodity"] == c]
    ax.plot(g["band_mid"], g["median_pct_gap"], color=COMMODITY_COLORS[c], marker="o", markersize=5, label=c)
viz.label_line_ends(ax, dist, "band_mid", "median_pct_gap", "commodity", fmt="{:.1f}%")
ax.set_xlabel("road distance between the two markets, km (20 km bands)")
ax.set_ylabel("median gap, % of lower price")
ax.set_ylim(0)
viz.legend(ax)
viz.save(fig, "q1_gap_by_distance", note="Road distance = straight-line distance x 1.3 (assumption).")
dist.pivot(index="road_km_band_start", columns="commodity", values="median_pct_gap")""",
        ),
        (
            "code",
            """\
mon = load("phase3", "q1_spread_monthly")
mon["month"] = pd.to_datetime(mon["month"])
fig, ax = viz.figure("Q1. Same-day gap between nearby markets over time",
                     "Monthly median gap as % of the lower price, pairs <= 100 km")
for c in COMMODITIES:
    g = mon[mon["commodity"] == c]
    ax.plot(g["month"], g["median_pct_gap"], color=COMMODITY_COLORS[c], label=c)
viz.label_line_ends(ax, mon, "month", "median_pct_gap", "commodity", fmt="{:.1f}%")
ax.set_ylabel("median gap, %")
ax.set_ylim(0)
viz.legend(ax)
viz.save(fig, "q1_gap_monthly")
mon.groupby("commodity")["median_pct_gap"].describe()""",
        ),
        ("md", "## Q2 - profitable moves after transport cost"),
        (
            "code",
            """\
q2 = load("phase3", "q2_opportunity_rate")
scen = ["low", "mid", "high"]
fig, ax = viz.figure("Q2. Market-days with a profitable nearby market, after transport and fees",
                     "% of market-days where >= 1 market within 100 km pays >= Rs 100/qtl and >= 5% more, net of transport and fees")
x = np.arange(len(scen))
w = 0.26
for i, c in enumerate(COMMODITIES):
    g = q2[q2["commodity"] == c].set_index("scenario").loc[scen]
    bars = ax.bar(x + (i - 1) * (w + 0.01), g["pct_market_days_with_opportunity"], width=w,
                  color=COMMODITY_COLORS[c], label=c)
    for b, v in zip(bars, g["pct_market_days_with_opportunity"], strict=True):
        ax.annotate(f"{v:.0f}%", (b.get_x() + b.get_width() / 2, v), xytext=(0, 3),
                    textcoords="offset points", ha="center", fontsize=8.5, color=INK_2)
ax.set_xticks(x, ["low cost\\n(Rs 1.0/qtl/km + 30, 4% fees)", "mid cost\\n(Rs 1.5/qtl/km + 50, 6% fees)", "high cost\\n(Rs 2.5/qtl/km + 80, 8% fees)"])
ax.set_ylabel("% of market-days")
ax.set_ylim(0, 70)
viz.legend(ax)
viz.save(fig, "q2_opportunity_rate_by_scenario",
         note="~8 neighbours report per day; any single one is profitable on only 5-20% of comparisons (see table). "
              "Fees 4/6/8%; spoilage not modelled.")
q2""",
        ),
        (
            "code",
            """\
gd = load("phase3", "q2_gain_distribution")
fig, ax = viz.figure("Q2. Size of the best gain on opportunity days (mid cost)",
                     "Share of opportunity market-days by best net gain, Rs per quintal (bins of 100; last bin = 2000+)")
for c in COMMODITIES:
    g = gd[gd["commodity"] == c].copy()
    g["share"] = 100 * g["n_market_days"] / g["n_market_days"].sum()
    ax.step(g["gain_bin_start_rs_qtl"], g["share"], where="post", color=COMMODITY_COLORS[c], label=c)
ax.set_xlabel("best net gain, Rs / quintal")
ax.set_ylabel("% of opportunity market-days")
ax.set_ylim(0)
viz.legend(ax)
viz.save(fig, "q2_gain_distribution")
gd.pivot(index="gain_bin_start_rs_qtl", columns="commodity", values="n_market_days").head(8)""",
        ),
        (
            "code",
            """\
yr = load("phase3", "q2_opportunity_by_year")
yr.pivot(index="year", columns="commodity", values="pct_market_days_with_opportunity")""",
        ),
        ("md", "## Sanity checks behind the Q2 number"),
        (
            "code",
            """\
for q in ["sanity_02_opportunity_concentration", "sanity_04_structural_vs_sporadic",
          "sanity_05_actionable_opportunities", "sanity_06_variety_mix", "sanity_07_opportunity_by_state"]:
    print(q)
    display(load("phase3", q))""",
        ),
    ],
    "03_seasonality_volatility.ipynb": [
        (
            "md",
            "# 03 - Seasonality, crashes and volatility (Q3, Q5)\n\n"
            "Q3: which months and crops crash predictably?  \n"
            "Q5: how does volatility differ between the perishable (tomato) and storables (onion, potato)?\n\n"
            "Crash (spec 9.2): within the next 14 days the price falls below 70% of its trailing 30-day median, "
            "computed only from days with data.",
        ),
        ("code", SETUP),
        ("md", "## Q3 - seasonal price pattern and crash rate by month"),
        (
            "code",
            """\
s = load("phase3", "q3_seasonality_by_month")
fig, ax = viz.figure("Q3. Seasonal price pattern by crop",
                     "Price index = month median / annual median (1.0 = a typical month), median across years and states")
for c in COMMODITIES:
    g = s[s["commodity"] == c]
    ax.plot(g["month"], g["median_price_index"], color=COMMODITY_COLORS[c], marker="o", markersize=5, label=c)
viz.label_line_ends(ax, s, "month", "median_price_index", "commodity", fmt="{:.2f}")
ax.axhline(1, color=MUTED, linewidth=0.8)
ax.set_xticks(range(1, 13), ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"])
ax.set_ylabel("price index (x annual median)")
viz.legend(ax)
viz.save(fig, "q3_price_index_by_month")
s.pivot(index="month", columns="commodity", values="median_price_index")""",
        ),
        (
            "code",
            """\
grid = s.pivot(index="commodity", columns="month", values="crash_rate_pct").loc[COMMODITIES]
fig, ax = viz.figure("Q3. How often prices crash, by month",
                     "% of market-days followed within 14 days by >= 2 days below 70% of the 30-day median", height=3.8)
cmap = LinearSegmentedColormap.from_list("seq", viz.SEQUENTIAL)
im = ax.imshow(grid.values, cmap=cmap, aspect="auto", vmin=0)
ax.grid(False)
ax.set_xticks(range(12), ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"])
ax.set_yticks(range(len(grid.index)), grid.index)
vmax = np.nanmax(grid.values)
for i in range(grid.shape[0]):
    for j in range(grid.shape[1]):
        v = grid.values[i, j]
        ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=8.5,
                color="white" if v > 0.55 * vmax else INK)
fig.colorbar(im, ax=ax, label="crash rate, %", shrink=0.8)
viz.save(fig, "q3_crash_rate_heatmap")
grid""",
        ),
        (
            "code",
            """\
display(load("phase3", "q3_crash_rate_by_state_month").pivot_table(
    index=["commodity", "state"], columns="month", values="crash_rate_pct"))
load("phase3", "q3_crash_lead")""",
        ),
        ("md", "## Q5 - volatility: perishable vs storable"),
        (
            "code",
            """\
v = load("phase3", "q5_volatility_by_commodity").set_index("commodity").loc[COMMODITIES].reset_index()
viz.style()
fig, axes = plt.subplots(1, 2, figsize=(10, 4.6))
viz.header(fig, "Q5. Price volatility: tomato vs onion and potato",
           "Median over market-years with >= 60 report days (main period)")
panels = [("median_cv", "coefficient of variation (std / mean)", "{:.2f}"),
          ("median_avg_abs_daily_change_pct", "average absolute day-to-day change, %", "{:.1f}%")]
for ax, (col, label, fmt) in zip(axes, panels, strict=True):
    bars = ax.bar(v["commodity"], v[col], color=[COMMODITY_COLORS[c] for c in v["commodity"]], width=0.55)
    for b, val in zip(bars, v[col], strict=True):
        ax.annotate(fmt.format(val), (b.get_x() + b.get_width() / 2, val), xytext=(0, 3),
                    textcoords="offset points", ha="center", fontsize=9, color=INK_2)
    ax.set_title(label, loc="left", fontsize=10, color=INK_2)
    ax.set_ylim(0)
viz.save(fig, "q5_volatility_by_commodity")
v""",
        ),
        (
            "code",
            """\
vy = load("phase3", "q5_volatility_by_year")
fig, ax = viz.figure("Q5. Volatility every year", "Median coefficient of variation of daily prices within a market-year")
for c in COMMODITIES:
    g = vy[vy["commodity"] == c]
    ax.plot(g["year"], g["median_cv"], color=COMMODITY_COLORS[c], marker="o", markersize=5, label=c)
viz.label_line_ends(ax, vy, "year", "median_cv", "commodity", fmt="{:.2f}")
ax.set_ylabel("median CV")
ax.set_ylim(0)
viz.legend(ax)
viz.save(fig, "q5_cv_by_year")
vy.pivot(index="year", columns="commodity", values="median_cv")""",
        ),
    ],
    "04_price_trapped_districts.ipynb": [
        (
            "md",
            "# 04 - Price-trapped districts (Q4)\n\n"
            "A district x crop is *price-trapped* when it has <= 2 distinct town locations with valid data within 50 km "
            "of its centre AND its average price is < 90% of the state price on the same days.",
        ),
        ("code", SETUP),
        (
            "code",
            """\
da = load("phase3", "q4_district_access")
summary = load("phase3", "q4_trapped_summary")
summary""",
        ),
        (
            "code",
            """\
viz.style()
fig, axes = plt.subplots(1, 3, figsize=(12, 4.6), sharey=True)
viz.header(fig, "Q4. District access vs price level",
           "Each dot = district x crop. Shaded corner = price-trapped (<= 2 towns within 50 km and price index < 0.9)")
rng = np.random.default_rng(0)
for ax, c in zip(axes, COMMODITIES, strict=True):
    g = da[da["commodity"] == c]
    jitter = rng.uniform(-0.25, 0.25, len(g))
    ax.fill_between([-0.5, 2.5], 0, 0.9, color=viz.GRID, alpha=0.7, linewidth=0)
    ax.scatter(g["n_markets_within_50km"] + jitter, g["avg_price_index"], s=22,
               color=COMMODITY_COLORS[c], edgecolor="white", linewidth=0.6)
    t = g[g["is_price_trapped"]]
    ax.scatter(t["n_markets_within_50km"] + rng.uniform(-0.25, 0.25, len(t)), t["avg_price_index"], s=40,
               facecolor="none", edgecolor=INK, linewidth=1.2)
    ax.axhline(0.9, color=MUTED, linewidth=0.8)
    ax.set_title(f"{c}  ({int(g['is_price_trapped'].sum())} trapped)", loc="left", fontsize=10, color=INK_2)
    ax.set_xlabel("town locations with data within 50 km")
axes[0].set_ylabel("avg price index (district / state, same days)")
axes[0].set_ylim(0.4, 1.6)
viz.save(fig, "q4_district_access_scatter",
         note="Ringed dots are price-trapped. District centres from OpenStreetMap; town locations = distinct market coordinates.")
da[da["is_price_trapped"]]""",
        ),
        ("md", "## Robustness of all headline numbers (Q1-Q5)"),
        (
            "code",
            """\
rob = load("phase3", "robustness")
rob.pivot_table(index=["question", "metric", "commodity"], columns="version", values="value")""",
        ),
    ],
}


def build() -> None:
    for name, cells in NOTEBOOKS.items():
        nb = nbf.v4.new_notebook()
        nb.metadata["kernelspec"] = {
            "name": "mandipulse",
            "display_name": "Python (mandipulse)",
            "language": "python",
        }
        nb.cells = [
            nbf.v4.new_markdown_cell(src) if kind == "md" else nbf.v4.new_code_cell(src)
            for kind, src in cells
        ]
        nbf.write(nb, HERE / name)
        print(f"wrote notebooks/{name}")


if __name__ == "__main__":
    build()
