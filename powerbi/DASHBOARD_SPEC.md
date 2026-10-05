# Mandi Pulse: Power BI dashboard, step by step

This guide builds the 5-page Power BI report described in spec Section 10.2. It assumes no prior Power BI experience. Claude Code cannot build the `.pbix` file, so you build it by following the steps below. The data comes from `python -m mandipulse export` (see [exports/README.md](../exports/README.md)).

**Time needed:** about 3–4 hours the first time.
**You need:** Power BI Desktop (free, Windows; Microsoft Store or microsoft.com/power-bi/desktop).

Every number in the "Check" boxes was computed from the same export files, so you can confirm that each measure is right.

---

## 0. Before you start

1. Run the export from the project folder (Postgres must be running):
   ```
   python -m mandipulse export
   ```
   It writes `exports/powerbi/*.parquet` (plus `.csv` copies) and `exports/manifest.csv`, which lists row counts and sizes.
2. Open Power BI Desktop → **File → Options and settings → Options**:
   - **Regional settings → Locale for import:** English (India). This gives ₹ and lakh/crore-friendly separators.
   - **Security → Map and Filled Map visuals:** tick "Use Map and Filled Map visuals" (needed for pages 2 and 4).
   - **Data Load → Time intelligence:** untick "Auto date/time". We use our own date table, and auto date tables bloat the file.

---

## 1. Import the data (Parquet connector)

Use **Home → Get data → More… → Parquet**. Paste the full path of each file, e.g. `C:\…\Mandi\exports\powerbi\dim_date.parquet`, then click **Load**. Repeat for each file in the table below. (Parquet keeps the column types; the `.csv` copies are only a fallback.)

| # | File (in `exports/powerbi/`) | Rows | What it is | Used on pages |
|---|---|---|---|---|
| 1 | `dim_date.parquet` | 3,032 | One row per calendar day, 2018-01-01 → 2026-04-20 | all |
| 2 | `dim_commodity.parquet` | 3 | Tomato, Onion, Potato (+ category) | all |
| 3 | `dim_market.parquet` | 595 | Market name, district, state, latitude/longitude | 1, 2 |
| 4 | `fact_daily_price.parquet` | 1,778,272 | One row per market × crop × day: modal / min / max price (₹/qtl) | 1, 3 |
| 5 | `mart_price_spread_daily.parquet` | 33,473 | Per day × crop × state: median and p90 price gap between markets ≤ 100 km apart | 1, 2 |
| 6 | `mart_price_spread_latest90.parquet` | 176,867 | Every market pair ≤ 100 km, last 90 days: both prices and the gap | 2 |
| 7 | `mart_opportunity_market_day_monthly.parquet` | 248,112 | Per month × market × crop × cost scenario: market-days and days with a profitable move | 1, 4 |
| 8 | `mart_net_price_opportunities_monthly.parquet` | 752,579 | Per month × home → destination × scenario: number of profitable days and the average gain | 1, 2 |
| 9 | `mart_seasonality.parquet` | 144 | Per crop × state × month: median price, price index, crash rate | 3 |
| 10 | `mart_volatility.parquet` | 7,215 | Per market × crop × year: CV, average daily % change, max drawdown | 3 |
| 11 | `mart_district_access.parquet` | 463 | Per district × crop: nearby markets, price index, opportunity rate, price-trapped flag, district centre lat/long | 4 |
| 12 | `ml_market_cluster.parquet` | 1,128 | Per market × crop: segment (cluster) name and its features | 4 |
| 13 | `ml_price_forecast_backtest.parquet` | 108,004 | Test months May–Oct 2025: actual, model p10/p50/p90 (calibrated), "last value" baseline | 5 |
| 14 | `ml_price_forecast.parquet` | 920 | Latest 7-day forecast per market × crop | 5 |
| 15 | `ml_crash_status_latest.parquet` | 920 | Latest price vs its 30-day median ("falling now") + model crash score | 5 |

**Optional files:**
- `mart_price_spread_monthly`, `mart_net_price_opportunities_latest90`, `mart_opportunity_market_day_latest90` and `ml_crash_risk` are also exported. Use them if you want extra drill-downs; the pages below don't need them.
- The three pair-level marts have 6.6–6.8 million rows each in Postgres. They are exported as **monthly aggregates + the latest 90 days of detail** so the report stays small (about 40 MB).

**After loading, check the column types** in the **Table view** (left bar, grid icon):
- `date`, `month`, `target_date`, `horizon_date` → **Date** (not Date/Time). Change it under **Column tools → Data type**.
- Price columns → **Decimal number**, format **Currency → ₹ English (India)**, 0 decimals.
- Rate / share columns (`opportunity_rate`, `crash_rate`, `price_index`, `avg_price_index`, `ratio_to_median`, `prob`, `cv`) → **Percentage**, 0–1 decimals.

---

## 2. Data model (relationships)

Go to **Model view** (left bar, the third icon). Power BI may auto-create some relationships. **Delete any that are not in the table below**, then drag a column from one table onto the other to create each one.

All relationships are **Many-to-one (\*:1), single cross-filter direction (dimension → fact)**, and **active** unless stated otherwise.

| From (many side) | To (one side) |
|---|---|
| `fact_daily_price[date_key]` | `dim_date[date_key]` |
| `fact_daily_price[market_key]` | `dim_market[market_key]` |
| `fact_daily_price[commodity_key]` | `dim_commodity[commodity_key]` |
| `mart_price_spread_daily[date]` | `dim_date[date]` |
| `mart_price_spread_daily[commodity]` | `dim_commodity[commodity]` |
| `mart_price_spread_latest90[date_key]` | `dim_date[date_key]` |
| `mart_price_spread_latest90[commodity_key]` | `dim_commodity[commodity_key]` |
| `mart_price_spread_latest90[market_key_a]` | `dim_market[market_key]` |
| `mart_opportunity_market_day_monthly[month]` | `dim_date[date]` |
| `mart_opportunity_market_day_monthly[commodity_key]` | `dim_commodity[commodity_key]` |
| `mart_opportunity_market_day_monthly[home_market_key]` | `dim_market[market_key]` |
| `mart_net_price_opportunities_monthly[month]` | `dim_date[date]` |
| `mart_net_price_opportunities_monthly[commodity_key]` | `dim_commodity[commodity_key]` |
| `mart_net_price_opportunities_monthly[home_market_key]` | `dim_market[market_key]` |
| `mart_seasonality[commodity]` | `dim_commodity[commodity]` |
| `mart_volatility[commodity]` | `dim_commodity[commodity]` |
| `mart_volatility[market_key]` | `dim_market[market_key]` |
| `mart_district_access[commodity]` | `dim_commodity[commodity]` |
| `ml_market_cluster[commodity_key]` | `dim_commodity[commodity_key]` |
| `ml_market_cluster[market_key]` | `dim_market[market_key]` |
| `ml_price_forecast_backtest[target_date]` | `dim_date[date]` |
| `ml_price_forecast_backtest[commodity_key]` | `dim_commodity[commodity_key]` |
| `ml_price_forecast_backtest[market_key]` | `dim_market[market_key]` |
| `ml_price_forecast[commodity_key]` | `dim_commodity[commodity_key]` |
| `ml_price_forecast[market_key]` | `dim_market[market_key]` |
| `ml_crash_status_latest[commodity]` | `dim_commodity[commodity]` |
| `ml_crash_status_latest[market_key]` | `dim_market[market_key]` |

Notes:
- `mart_price_spread_latest90[market_key_b]` → `dim_market[market_key]` can be added as an **inactive** relationship (dotted line); Power BI allows only one active path. It isn't needed below.
- `ml_price_forecast` is **not** linked to `dim_date`, because its `horizon_date` (early Nov 2025) is after the analysis period.
- `mart_seasonality` and `mart_district_access` have a `state` column but no market key, so use their own `state` column as a slicer on the pages that use them.

**Mark the date table:** select `dim_date` → **Table tools → Mark as date table** → column `date`. This makes the year-on-year measures work.

**Sort month names:** select `dim_date[month_name]` → **Column tools → Sort by column → `month`**. Do the same for `mart_seasonality[month_name]` (sort by `mart_seasonality[month]`).

**Hide keys:** right-click each `*_key` column → **Hide in report view**. This keeps the field list clean.

**One report-level filter (important):** in the **Filters** pane → **Filters on all pages**, drag `dim_date[period]` and select **main**. The source changed its market naming from Nov 2025, and that data is not used in the analysis (the app's banner says the same). With this filter, the market-day count matches the app: **1,757,149**.

---

## 3. Measures (DAX)

Create a blank table to hold the measures:
- **Home → Enter data**, name it `_Measures`, click **Load**.
- Then select it and use **New measure** for each block below.
- Delete its dummy `Column1` after the first measure exists.

The spec's starter measures are updated here for two later decisions:
- **Fees:** the gain is already **after transport and commission/market fees** (4 / 6 / 8% of the destination price in the low / mid / high scenario).
- **Crash definition:** on ≥ 2 report days in the next 14, the price is below 70% of its trailing 30-day median.

```DAX
// ---------- prices ----------
Market-Days =
CALCULATE ( COUNTROWS ( fact_daily_price ),
            NOT ISBLANK ( fact_daily_price[modal_price] ),
            fact_daily_price[is_suspect_low] = FALSE () )
// Check: 1,757,149 (with the period = "main" report filter)

Markets Tracked =
CALCULATE ( DISTINCTCOUNT ( fact_daily_price[market_key] ),
            NOT ISBLANK ( fact_daily_price[modal_price] ) )
// Check: 594

Days of Data =
DATEDIFF ( MIN ( dim_date[date] ), MAX ( dim_date[date] ), DAY ) + 1
// Check: 2,861 (2018-01-01 to 2025-10-31)

Median Modal Price =
CALCULATE ( MEDIAN ( fact_daily_price[modal_price] ),
            fact_daily_price[is_suspect_low] = FALSE () )

Price YoY % =
VAR curr = [Median Modal Price]
VAR prev = CALCULATE ( [Median Modal Price], SAMEPERIODLASTYEAR ( dim_date[date] ) )
RETURN DIVIDE ( curr - prev, prev )

// ---------- price gaps (Q1) ----------
Typical Same-Day Gap =
MEDIAN ( mart_price_spread_daily[median_abs_gap] )
// "median of the daily median gaps" between markets <= 100 km apart, Rs/qtl

Typical Same-Day Gap % =
MEDIAN ( mart_price_spread_daily[median_pct_gap] )

// ---------- opportunities after transport AND fees (Q2) ----------
// SELECTEDVALUE lets a Scenario slicer drive the measure; without a slicer it uses "mid".
Selected Scenario =
SELECTEDVALUE ( mart_opportunity_market_day_monthly[scenario], "mid" )

Opportunity Rate =
VAR s = [Selected Scenario]
RETURN
DIVIDE (
    CALCULATE ( SUM ( mart_opportunity_market_day_monthly[n_opportunity_days] ),
                mart_opportunity_market_day_monthly[scenario] = s ),
    CALCULATE ( SUM ( mart_opportunity_market_day_monthly[n_market_days] ),
                mart_opportunity_market_day_monthly[scenario] = s )
)
// Share of market-days (with at least one neighbour <= 100 km reporting) on which some
// neighbour paid more after transport + fees, by >= Rs 100/qtl and >= 5%.
// Check: low 42.2%, mid 33.8%, high 24.4%

Opportunity Rate (Mid) =
CALCULATE ( [Opportunity Rate], mart_opportunity_market_day_monthly[scenario] = "mid" )

Avg Gain When Opportunity (Mid) =
VAR t = FILTER ( mart_net_price_opportunities_monthly,
                 mart_net_price_opportunities_monthly[scenario] = "mid" )
RETURN
DIVIDE (
    SUMX ( t, mart_net_price_opportunities_monthly[avg_gain]
              * mart_net_price_opportunities_monthly[n_opportunity_days] ),
    SUMX ( t, mart_net_price_opportunities_monthly[n_opportunity_days] )
)
// Weighted average gain per destination-day, Rs/qtl, after transport and 6% fees.
// Check: about Rs 446/qtl

// ---------- seasonality / crashes (Q3) ----------
Crash Rate =
DIVIDE ( SUM ( mart_seasonality[n_crash_days] ), SUM ( mart_seasonality[n_labelled_days] ) )
// Check by crop: Tomato 21.4%, Onion 11.7%, Potato 6.0%

Avg Price Index =
AVERAGE ( mart_seasonality[price_index] )

Avg Volatility (CV) =
AVERAGE ( mart_volatility[cv] )

Avg Daily Move % =
AVERAGE ( mart_volatility[avg_abs_daily_pct_change] )

// ---------- access (Q4) ----------
Price-Trapped Districts =
CALCULATE ( COUNTROWS ( mart_district_access ), mart_district_access[is_price_trapped] = TRUE () )

Districts =
COUNTROWS ( mart_district_access )

// ---------- forecast (Model A) ----------
Forecast MAE (Model) =
AVERAGEX ( ml_price_forecast_backtest,
           ABS ( ml_price_forecast_backtest[actual_price] - ml_price_forecast_backtest[p50] ) )
// Check: Rs 147.6/qtl (all test rows)

Forecast MAE (Same as Today) =
AVERAGEX ( ml_price_forecast_backtest,
           ABS ( ml_price_forecast_backtest[actual_price] - ml_price_forecast_backtest[baseline_last_value] ) )
// Check: Rs 158.6/qtl

Forecast Improvement % =
DIVIDE ( [Forecast MAE (Same as Today)] - [Forecast MAE (Model)], [Forecast MAE (Same as Today)] )
// Check: 6.9%

Band Coverage =
AVERAGEX ( ml_price_forecast_backtest,
           IF ( ml_price_forecast_backtest[actual_price] >= ml_price_forecast_backtest[p10]
                && ml_price_forecast_backtest[actual_price] <= ml_price_forecast_backtest[p90], 1, 0 ) )
// Check: 77.3% (target 80%)

// ---------- crash alerts (Model B + rule) ----------
Falling Now =
CALCULATE ( COUNTROWS ( ml_crash_status_latest ),
            ml_crash_status_latest[ratio_to_median] < 0.9,
            ml_crash_status_latest[is_suspect_series] = FALSE () )

Early Warnings (High) =
CALCULATE ( COUNTROWS ( ml_crash_status_latest ),
            ml_crash_status_latest[ratio_to_median] >= 0.9,
            ml_crash_status_latest[is_suspect_series] = FALSE (),
            FILTER ( ml_crash_status_latest,
                     ml_crash_status_latest[prob] >= ml_crash_status_latest[threshold] ) )
// Check: 4

Risk Level =
VAR p = SELECTEDVALUE ( ml_crash_status_latest[prob] )
VAR t = SELECTEDVALUE ( ml_crash_status_latest[threshold] )
RETURN SWITCH ( TRUE (), ISBLANK ( p ), BLANK (), p >= t, "High", p >= t / 2, "Medium", "Low" )

Data As Of =
"Data as of " & FORMAT ( CALCULATE ( MAX ( dim_date[date] ),
                                     FILTER ( ALL ( dim_date ), dim_date[period] = "main" ) ),
                        "dd mmm yyyy" )
        & " (latest available in the source archive)"
```

**Formatting the measures** (select a measure → **Measure tools**):
- ₹ measures (`Median Modal Price`, gaps, gains, MAEs): Currency ₹, 0 decimals.
- Rates, `%` measures, `Band Coverage`: Percentage, 1 decimal.
- Counts: Whole number with thousands separator.

---

## 4. Theme and layout

Save this as `mandipulse_theme.json`, then apply it with **View → Themes → Browse for themes**. It uses the same colours as the Streamlit app: tomato = blue, onion = orange, potato = green.

```json
{
  "name": "Mandi Pulse",
  "dataColors": ["#2A78D6", "#EB6834", "#1BAF7A", "#0B0B0B", "#898781", "#CDE2FB", "#F2C14E", "#7A4FD6"],
  "background": "#FFFFFF",
  "foreground": "#0B0B0B",
  "tableAccent": "#2A78D6",
  "good": "#1BAF7A",
  "neutral": "#F2C14E",
  "bad": "#D64545",
  "maximum": "#2A78D6",
  "center": "#F7F7F5",
  "minimum": "#EB6834",
  "textClasses": {
    "title": { "fontFace": "Segoe UI Semibold", "fontSize": 14, "color": "#0B0B0B" },
    "label": { "fontFace": "Segoe UI", "fontSize": 10, "color": "#3A3A38" },
    "callout": { "fontFace": "Segoe UI Semibold", "fontSize": 28, "color": "#0B0B0B" }
  }
}
```

**Same on every page:**
- Canvas 16:9 (default 1280 × 720).
- A **title text box** at the top left with the page's question (given below).
- At the top right, a **card** showing `[Data As Of]` (font 10, grey, no category label).
- **Slicers** in a column on the left, **Commodity** first. Set each slicer to **Dropdown** style, with "Select all" enabled.
- **Sync slicers:** View → Sync slicers. Sync `dim_commodity[commodity]` across all 5 pages, so a crop chosen on one page stays chosen.
- Turn off visual borders and use light gridlines. Show units in every axis title: "₹ per quintal".
- **Fixed crop colours:** in every chart that uses Commodity as the legend, open **Format → Colors** and set Tomato `#2A78D6`, Onion `#EB6834`, Potato `#1BAF7A`.

---

## 5. The five pages

### Page 1: Overview
**Question this page answers:** *"How big are the price differences between nearby mandis, and how often does it pay to sell elsewhere?"*

| Visual | Fields | Settings |
|---|---|---|
| 5 × **Card** across the top | `[Markets Tracked]`, `[Days of Data]`, `[Typical Same-Day Gap]`, `[Opportunity Rate (Mid)]`, `[Avg Gain When Opportunity (Mid)]` | Rename each (double-click the field in the Fields well): "Markets tracked", "Days of data", "Typical gap to a market ≤ 100 km (₹/qtl)", "Days a nearby market paid more (mid costs)", "Average extra ₹/qtl when it did" |
| **Line chart** (left, large) | X: `dim_date[date]` (Date hierarchy **off**, continuous axis); Y: `[Typical Same-Day Gap]`; Legend: `dim_commodity[commodity]` | Title "Typical gap between markets ≤ 100 km apart, ₹/qtl". The X axis is continuous. Add an average line (Analytics pane) |
| **Clustered column chart** (right) | X: `dim_commodity[commodity]`; Y: `[Opportunity Rate]`; slicer for scenario below | Title "Share of market-days with a better nearby market, after transport and fees". Data labels on |
| **Slicer** | `mart_opportunity_market_day_monthly[scenario]` | Single select, buttons (tile) style, values low / mid / high, default **mid** |
| **Slicers** | `dim_commodity[commodity]`, `dim_market[state]`, `dim_date[year]` | Dropdown; year as a "Between" slider |
| **Text box** (bottom) | – | "Costs: freight ₹1.0 / 1.5 / 2.5 per qtl per km + handling ₹30 / 50 / 80 per qtl + fees 4 / 6 / 8% of sale (low / mid / high). Road distance = straight line × 1.3." |

**Check** (all crops, all years): 594 markets; 33.8% mid; about ₹446.

### Page 2: Price Spread Explorer
**Question:** *"Where are the gaps right now, and between which markets?"*

| Visual | Fields | Settings |
|---|---|---|
| **Map** (Bing map visual, large, left) | Latitude `dim_market[latitude]`; Longitude `dim_market[longitude]`; Bubble size `[Median Modal Price]`; Legend `dim_commodity[commodity]`; Tooltips `dim_market[market]`, `dim_market[district]`, `[Median Modal Price]` | Map style "Light"; bubble size about 30%; auto-zoom on. Bigger bubble = higher typical price |
| **Table** (right): biggest gaps, last 90 days | From `mart_price_spread_latest90`: `date`, `commodity`, `dim_market[market]` (market A, via the relationship), `market_key_b`, `road_km_est`, `price_a`, `price_b`, `abs_gap`, `pct_gap` | Sort by `abs_gap` descending; **Top N filter = 25** by `abs_gap`; conditional formatting → data bars on `abs_gap`. Rename the headers to plain words ("Gap ₹/qtl", "Road km") |
| **Bar chart**: top 15 destinations by profitable days | Y: `mart_net_price_opportunities_monthly[dest_market_key]` (or add `dim_market[market]` via a lookup column, see below); X: Sum of `n_opportunity_days` | Filter scenario = mid; Top N 15 |
| **Slicers** | `dim_commodity[commodity]`, `dim_market[state]`, `dim_date[date]` (Between) | |

**Tip:** to show the destination market's *name*, add a calculated column to `mart_price_spread_latest90`:
```DAX
Market B = LOOKUPVALUE ( dim_market[market], dim_market[market_key], mart_price_spread_latest90[market_key_b] )
```
Do the same for `mart_net_price_opportunities_monthly[dest_market_key]` (column name `Destination`).

### Page 3: Seasonality & Volatility
**Question:** *"When in the year do prices peak and crash, and which crops are most volatile?"*

| Visual | Fields | Settings |
|---|---|---|
| **Matrix** as a heatmap (top left) | Rows: `mart_seasonality[commodity]`; Columns: `mart_seasonality[month_name]` (sorted by month); Values: `[Avg Price Index]` | Conditional formatting → Background color → **Gradient**: lowest `#EB6834` (orange), centre 1.0 `#F7F7F5`, highest `#2A78D6` (blue). Format the values as %. Title "Price vs the crop's yearly average (100% = average)" |
| **Matrix** as a heatmap (top right) | Same rows and columns; Values: `[Crash Rate]` | Gradient white → `#D64545`. Title "Share of report days followed by a crash". December stands out |
| **Line chart** (bottom left) | X: `dim_date[month_name]`; Y: `[Median Modal Price]`; Legend: `dim_commodity[commodity]` | Title "Median price by month, ₹/qtl" |
| **Clustered bar chart** (bottom right) | Y: `mart_volatility[commodity]`; X: `[Avg Volatility (CV)]` and `[Avg Daily Move %]` | Title "Volatility: tomato (perishable) vs onion/potato (storable)" |
| **Slicers** | `mart_seasonality[state]`, `mart_volatility[year]` | |

**Check:** crash rate tomato 21.4%, onion 11.7%, potato 6.0%.

### Page 4: Price-Trapped Districts
**Question:** *"Which districts have few nearby markets and get lower prices?"*

| Visual | Fields | Settings |
|---|---|---|
| **Map** (left) | Latitude `mart_district_access[latitude]`; Longitude `mart_district_access[longitude]` (district centre = average of its markets); Bubble size `mart_district_access[n_markets_within_50km]`; Legend `mart_district_access[is_price_trapped]`; Tooltips district, `avg_price_index`, `opportunity_rate` | Colors: True = `#D64545`, False = `#898781`. Title "Districts: red = price-trapped" |
| **Card** | `[Price-Trapped Districts]` and `[Districts]` | Title "Price-trapped districts" |
| **Table** | `state`, `district`, `commodity`, `n_markets_within_50km`, `avg_price_index`, `opportunity_rate`, `is_price_trapped` | Filter `is_price_trapped` = True; sort `avg_price_index` ascending. Rename the headers: "Market towns ≤ 50 km", "Price vs state", "Days a nearby market paid more" |
| **Donut chart** | Legend `ml_market_cluster[cluster_name]`; Values Count of `market_key` | Title "Market segments (k-means)" |
| **Table** | `dim_market[market]`, `dim_market[district]`, `ml_market_cluster[cluster_name]`, `price_index`, `report_freq`, `crash_rate` | |
| **Slicers** | `mart_district_access[state]`, `dim_commodity[commodity]` | |

**Definition (text box):** "Price-trapped = at most 2 market towns within 50 km, and an average price below 90% of the state level. Some market locations are only approximate (district centre)."

### Page 5: Forecast & Alerts
**Question:** *"How good is the 7-day forecast, and which markets need watching now?"*

| Visual | Fields | Settings |
|---|---|---|
| 4 × **Card** | `[Forecast MAE (Model)]`, `[Forecast MAE (Same as Today)]`, `[Forecast Improvement %]`, `[Band Coverage]` | Titles: "Model error ₹/qtl", "'Next week = today' error", "Improvement", "Range contains the actual (target 80%)" |
| **Line chart** (large) | X: `ml_price_forecast_backtest[target_date]`; Y: Sum of `actual_price`, Sum of `p50`, Sum of `baseline_last_value`, Sum of `p10`, Sum of `p90` | **Select one market** with the slicer below, otherwise the sums are meaningless. Colours: actual `#0B0B0B`; p50 `#2A78D6`; baseline `#EB6834` dashed; p10/p90 `#CDE2FB` thin dotted. (Power BI's line chart has no shaded band; the dotted p10/p90 lines show the range.) Title "Actual vs 7-day forecast, test months May–Oct 2025" |
| **Slicer** (single select) | `dim_market[market]` + `dim_commodity[commodity]` | Single select on; search on |
| **Table: "Falling now"** | `ml_crash_status_latest`: market (via `dim_market[market]`), `commodity`, `modal_price`, `median_30d`, `ratio_to_median`, `date` | Visual-level filters `ratio_to_median` < 0.9 and `is_suspect_series` = False; sort `ratio_to_median` ascending. Header "Below 90% of the 30-day median (rule, no model)" |
| **Table: "Early warning"** | Same table: market, `commodity`, `prob`, `[Risk Level]`, `modal_price`, `median_30d`, `date` | Filters `ratio_to_median` ≥ 0.9 and `is_suspect_series` = False; sort `prob` descending; Top N 20. Conditional formatting on `prob`: background gradient white → `#D64545` |
| **Text box** under the early-warning table | – | "**About 3 in 10 early warnings come true, typically ~6.6 days ahead.** Ranking quality on not-yet-falling days: PR-AUC 0.29 vs 0.15 for a seasonal rule (0.25 vs 0.07 outside December). Use it as a prompt to watch prices, not as a certainty." |

**Check:** model ₹147.6, same-as-today ₹158.6, improvement 6.9%, coverage 77.3%, High early warnings 4.

---

## 6. Finishing touches

- **Page names** (double-click the tabs): Overview · Price Spread · Seasonality · Price-Trapped · Forecast & Alerts.
- **Tooltips:** for every visual, check that the tooltip shows units (₹/qtl), not raw column names.
- **Performance:** **View → Performance analyzer → Start recording**, then click through every page. Every visual should take under 2 seconds. If `fact_daily_price` visuals are slow, add a report filter `dim_date[year] >= 2021`.
- **Save** as `powerbi/mandi_pulse.pbix`. It is about 40–60 MB, so **don't commit it** (it is not in git); share it via a release or OneDrive link.
- **Refreshing:** re-run `python -m mandipulse export`, then **Home → Refresh** in Power BI.

---

## 7. Screenshot checklist for the README

Save the screenshots as PNG, 1600 px wide, into `reports/figures/powerbi/`. Use **File → Export → Export to PDF** for a full-page version, or Windows **Snipping Tool** for single pages. Each screenshot should be:

- [ ] **01_overview.png**: all crops, all years, scenario = mid. All 5 KPI cards visible and the gap trend line showing the 2023 tomato spike.
- [ ] **02_price_spread.png**: Commodity = Tomato, State = Maharashtra. The map zoomed to Maharashtra, with the top-25 gap table.
- [ ] **03_seasonality.png**: all crops. Both heatmaps visible; the December crash column should be clearly red.
- [ ] **04_price_trapped.png**: Commodity = Tomato. Map with red trapped districts plus the trapped-district table.
- [ ] **05_forecast_alerts.png**: one market that reported almost every test day (for example **Fatehpur** or **Etawah**, Uttar Pradesh) and Tomato. Forecast chart plus both alert tables and the honesty note.
- [ ] Before each capture, check that the "Data as of 31 Oct 2025" card is visible.
- [ ] Hide the Filters pane (**View → Filters pane** off) for clean shots.
- [ ] Before taking the shots, check that each **Check** number in this guide matches what you see on the page.
- [ ] Add the PNGs to the README under "Dashboard" with one sentence each, saying what the page answers.
