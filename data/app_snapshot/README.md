# data/app_snapshot/

A small Parquet snapshot (about 2.7 MB) of the datasets the Streamlit app reads. The deployed app (Streamlit Community Cloud) uses it with `DATA_BACKEND=parquet`, so it needs no database. A fresh clone without a database uses it automatically.

- **Contents:** one file per dataset in `mandipulse.serving.DATASETS`: `meta`, `markets`, `latest_prices`, `suspect_series`, `price_history` (last 200 days), `forecast_latest`, `forecast_backtest` (May–Oct 2025 test months), `crash_status`, `district_access`, `clusters`. These are aggregates and model outputs derived from the cleaned marts; no raw archive rows are included.
- **Data as of:** 31 Oct 2025, the last day of the analysis period.
- **Refresh:** `python -m mandipulse export --snapshot` (or `python -m mandipulse pipeline --snapshot`). It is produced by the same SQL as the Postgres backend; `tests/test_serving.py` checks that the two backends match.

## Attribution and licence

Derived from **Agmarknet** daily wholesale prices, published by the Directorate of Marketing & Inspection (DMI), Ministry of Agriculture & Farmers Welfare, Government of India, obtained through the Kaggle archive [*Daily Market Prices of Commodity India (2001–2026)*](https://www.kaggle.com/datasets/khandelwalmanas/daily-commodity-prices-india) (khandelwalmanas).

- Licence: [Government Open Data License – India (GODL)](https://data.gov.in/government-open-data-license-india). Reuse is permitted with attribution.
- The cleaning, aggregation and model outputs are by Mandi Pulse; they are not official government figures.
- Market coordinates: © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors, ODbL.
