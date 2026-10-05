# exports/

Written by `python -m mandipulse export` from the Postgres marts and ml tables. Everything here is gitignored **except this README and `manifest.csv`** (row counts and sizes of the last export). Re-run the command after `dbt build` or `ml score`.

Set `MANDIPULSE_EXPORT_DIR` to write somewhere else (CI and test runs use a throwaway folder).

Last export (2026-10-05): 29 files, 45.2 MB Parquet. The CSV copies of the Power BI tables total about 477 MB.

## `powerbi/`: for Power BI (Parquet + an identical CSV)

How to use these files: [powerbi/DASHBOARD_SPEC.md](../powerbi/DASHBOARD_SPEC.md). Prices are in ₹ per quintal (100 kg). Full column definitions: [docs/DATA_DICTIONARY.md](../docs/DATA_DICTIONARY.md).

| File | Rows | Parquet MB | Grain / contents |
|---|---|---|---|
| `dim_date` | 3,032 | 0.04 | one row per day, 2018-01-01 → 2026-04-20; `period` = main / post_format_change |
| `dim_commodity` | 3 | 0.00 | Tomato, Onion, Potato + category |
| `dim_market` | 595 | 0.07 | market, district, state, lat/long, `geo_precision`, town, report counts |
| `fact_daily_price` | 1,778,272 | 18.1 | market × crop × day: modal/min/max price (and `_incl_suspect` versions), suspect flag, period |
| `mart_seasonality` | 144 | 0.01 | crop × state × month: median price, price index, crash days / labelled days |
| `mart_volatility` | 7,215 | 0.18 | market × crop × year: CV, average absolute daily % change, max drawdown |
| `mart_district_access` | 463 | 0.03 | district × crop: markets within 50 km, price index, opportunity rate, price-trapped flag, **district centre lat/long** (mean of its geocoded markets; added in the export) |
| `mart_price_spread_daily` | 33,473 | 0.40 | day × crop × state: median / p90 gap between markets ≤ 100 km apart |
| `mart_price_spread_monthly` | 424,012 | 4.7 | **aggregate** of `mart_price_spread` (6.6 M rows): month × market pair × crop: days, avg absolute gap, median % gap |
| `mart_price_spread_latest90` | 176,867 | 2.3 | **detail** of `mart_price_spread`, last 90 days of data |
| `mart_net_price_opportunities_monthly` | 752,579 | 8.2 | **aggregate**: month × scenario × home → destination × crop: profitable days, avg and max gain (after transport + fees) |
| `mart_net_price_opportunities_latest90` | 112,484 | 2.6 | **detail**, last 90 days |
| `mart_opportunity_market_day_monthly` | 248,112 | 2.0 | **aggregate**: month × scenario × home market × crop: market-days, days with an opportunity, rate, avg best gain |
| `mart_opportunity_market_day_latest90` | 143,250 | 1.4 | **detail**, last 90 days |
| `ml_price_forecast` | 920 | 0.04 | latest 7-day forecast per market × crop: p10/p50/p90 (calibrated band) |
| `ml_price_forecast_backtest` | 108,004 | 2.2 | test months May–Oct 2025: actual, model p10/p50/p90 (calibrated), "last value" baseline |
| `ml_crash_risk` | 920 | 0.03 | latest crash score per market × crop, alert flag, threshold |
| `ml_market_cluster` | 1,128 | 0.06 | market × crop segment (k-means, k=5) and its features |
| `ml_crash_status_latest` | 920 | 0.04 | latest report per series (within 14 days of the data end): price, 30-day median, ratio ("falling now" < 0.9), crash score, suspect flag |

The pair-level marts (6.6–6.8 M rows each) are **not** exported in full. Instead each has a monthly aggregate plus the latest 90 days of detail, which keeps the Power BI file small. The full tables stay in Postgres (`marts.*`) for direct connection.

## `app/`: Parquet backend of the Streamlit app

One file per dataset in `mandipulse.serving.DATASETS`, produced by **the same SQL** that the Postgres backend runs. `tests/test_serving.py` checks that both backends return identical tables. Deploy the app with `DATA_BACKEND=parquet` and this folder (2.6 MB); no database is needed.

| File | Rows | Contents |
|---|---|---|
| `meta` | 1 | first / last analysis date, market-days (the "data as of" banner) |
| `markets` | 594 | markets with valid data and their location |
| `latest_prices` | 999 | latest price per market × crop in the last 30 days |
| `suspect_series` | 22 | market × crop series flagged persistently low (excluded from recommendations) |
| `price_history` | 125,258 | last 200 days of prices |
| `forecast_latest` | 920 | = `ml_price_forecast` with the crop name |
| `forecast_backtest` | 108,004 | = `ml_price_forecast_backtest` with the crop name |
| `crash_status` | 920 | = `ml_crash_status_latest` |
| `district_access` | 463 | district access table |
| `clusters` | 1,128 | segments with market names |

## `manifest.csv`

Every file from the last run with its row count and Parquet/CSV size in MB.
