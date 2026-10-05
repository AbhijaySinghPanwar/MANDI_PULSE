# Mandi Pulse

"Google Flights for farmers' vegetable prices": which mandi gives the best *net* price for a crop this week, early warning before prices crash, and which districts are structurally stuck with bad prices.

Status: **Phase 5 done (Streamlit app, exports, Power BI guide)**. Findings: [reports/PHASE3_FINDINGS.md](reports/PHASE3_FINDINGS.md); ML results: [reports/ML_REPORT.md](reports/ML_REPORT.md). Power BI guide: [powerbi/DASHBOARD_SPEC.md](powerbi/DASHBOARD_SPEC.md); export files: [exports/README.md](exports/README.md). Progress log: [PROGRESS.md](PROGRESS.md). Data: [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md), [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md). Plan: [MANDI_PULSE_SPEC.md](MANDI_PULSE_SPEC.md).

## Quick start (so far)

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv -e ".[dev,dbt,notebooks,ml,app]"
cp .env.example .env
docker compose up -d                       # Postgres 16
python -m mandipulse profile-kaggle        # Phase 0 data profile (DuckDB on the Parquet archive)
python -m mandipulse load                  # Kaggle slice -> Postgres raw.mandi_prices (idempotent)
python -m mandipulse dbt build             # staging, quality flags, star schema, analysis marts + tests
python -m mandipulse queries phase3        # every reported number -> reports/tables/phase3/
python -m nbconvert --to notebook --execute --inplace notebooks/0*.ipynb   # figures -> reports/figures/
python -m mandipulse ml train-all          # forecast, crash warning, clusters, SHAP (~1 h)
python -m mandipulse ml score              # latest dates -> ml.price_forecast / crash_risk / market_cluster
python -m mandipulse ml validate-forecast  # pre-test check of the objective + band calibration (~40 min)
python -m mandipulse ml report             # reports/ML_REPORT.md from the saved metrics
python -m mandipulse export                # exports/powerbi (Parquet + CSV) and exports/app (Parquet)
streamlit run app/Home.py                  # the app, reading Postgres
DATA_BACKEND=parquet streamlit run app/Home.py   # the app, reading exports/app only (no database)
```

On Windows PowerShell, set the backend with `$env:DATA_BACKEND = "parquet"` before `streamlit run`.

The raw Kaggle archive is not in git: download "Daily Market Prices of Commodity India (2001-2026)" (GODL-India licence) from Kaggle and put the yearly Parquet files in `data/raw/kaggle/`.
