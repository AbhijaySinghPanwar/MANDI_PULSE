# Mandi Pulse

"Google Flights for farmers' vegetable prices": which mandi gives the best *net* price for a crop this week, early warning before prices crash, and which districts are structurally stuck with bad prices.

Status: **Phase 0 (setup + data profiling)**. See [PROGRESS.md](PROGRESS.md), [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) and the full plan in [MANDI_PULSE_SPEC.md](MANDI_PULSE_SPEC.md).

## Quick start (so far)

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv -e ".[dev]"
cp .env.example .env
docker compose up -d                       # Postgres 16
python -m mandipulse profile-kaggle        # re-runs the Phase 0 data profile
```

The raw Kaggle archive (`csv/`, `parquet/`) is not in git; download it from Kaggle ("Daily Market Prices of Commodity India (2001-2026)", GODL-India licence) into the project root.
