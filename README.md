# Mandi Pulse

"Google Flights for farmers' vegetable prices": which mandi gives the best *net* price for a crop this week, early warning before prices crash, and which districts are structurally stuck with bad prices.

Status: **Phase 3 done (analysis marts, EDA, findings)**. Findings: [reports/PHASE3_FINDINGS.md](reports/PHASE3_FINDINGS.md). Progress log: [PROGRESS.md](PROGRESS.md). Data: [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md), [docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md). Plan: [MANDI_PULSE_SPEC.md](MANDI_PULSE_SPEC.md).

## Quick start (so far)

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv -e ".[dev,dbt,notebooks]"
cp .env.example .env
docker compose up -d                       # Postgres 16
python -m mandipulse profile-kaggle        # Phase 0 data profile (DuckDB on the Parquet archive)
python -m mandipulse load                  # Kaggle slice -> Postgres raw.mandi_prices (idempotent)
python -m mandipulse dbt build             # staging, quality flags, star schema, analysis marts + tests
python -m mandipulse queries phase3        # every reported number -> reports/tables/phase3/
python -m nbconvert --to notebook --execute --inplace notebooks/0*.ipynb   # figures -> reports/figures/
```

The raw Kaggle archive is not in git: download "Daily Market Prices of Commodity India (2001-2026)" (GODL-India licence) from Kaggle and put the yearly Parquet files in `data/raw/kaggle/`.
