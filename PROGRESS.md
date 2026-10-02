# Progress

## Phase 0: Setup & data-access spike (2026-10-02)

### Done
- `.gitignore` written **before** `git init`. `csv/`, `parquet/`, `*.parquet`, `data/raw/`, `models/`, `exports/`, and `.env` are ignored. Verified with `git check-ignore`.
- Repo skeleton per spec Section 11: `pyproject.toml`, `docker-compose.yml` (Postgres 16), `.env.example`, `config/settings.yaml` (Section 17 + new `sources` block), `docs/`, empty package/dbt/app/report folders, CI stub (`.github/workflows/ci.yml`: ruff + pytest; dbt job commented out until Phase 2).
- Python 3.11 venv via `uv` (`.venv`). The system Python is 3.14, which the spec doesn't target.
- Kaggle archive profiled with DuckDB, querying the Parquet files in place (nothing loaded into pandas):
  - 22 saved queries in `analysis/queries/phase0/`, plus a CSV/Parquet parity check.
  - Runner: `python -m mandipulse profile-kaggle [--check-csv]` (≈15 s).
  - Outputs in `reports/tables/phase0/`. Write-up in `docs/DATA_SOURCES.md`.
- Spec Section 6 rewritten for the new source order: Kaggle (history) → CEDA (cross-check + arrivals) → data.gov.in (daily, later).
- `pytest` (3 config smoke tests) and `ruff check` / `ruff format --check` pass.

### Not done / deviations from the Phase 0 acceptance criteria
- **`docker compose up` was not run.** Docker Desktop's engine wasn't running on this machine. `docker compose config` validates the file. To finish: start Docker Desktop, then `docker compose up -d`.
- **No data.gov.in call** (user instruction: the site is unreachable). The resource ID stays unverified.
- **No CEDA call** (token not yet provided).
- **Spec §6.3 data.gov.in "rule"**: the instruction was cut off. A `TODO` placeholder is in the spec.

### Key findings (details and numbers in docs/DATA_SOURCES.md)
1. 75984017 rows, 2001-01-10 → 2026-04-21. CSV and Parquet match exactly. The **archive ends 5½ months before today**.
2. Commodity and state spellings match the spec exactly. Exclude the look-alikes `Onion Green` and `Sweet Potato`.
3. **Source change in Nov 2025:** markets renamed `X` → `X APMC`, and reporting density falls from ~28–30 to ~4–9 days/month. It had already been thinning since Jul 2025.
4. **Tamil Nadu:** almost no Tomato/Onion/Potato data from 2013 to mid-2024. Since then about 92% of rows come from Uzhavar Sandhai (near-retail) markets, and the other markets often enter prices in ₹/kg.
5. **Karnataka and Madhya Pradesh** look complete at state level but are thin at market level (median 34–52 report days per series over 2023-11 → 2025-10; Karnataka tomato 152). MP has a hole in Jan–Sep 2024.
6. Quality: zero min/max placeholders are 2.4% overall but <0.5% a year from 2018. In scope: 136 exact duplicates (none conflicting), no null or zero modal prices.

### Decisions needed
Recommendation (reasons in docs/DATA_SOURCES.md §4). **Not applied to `config/settings.yaml` yet; waiting for the user's decision.**
- **Crops:** keep Tomato, Onion, Potato.
- **States:** Maharashtra, Madhya Pradesh, **Uttar Pradesh**, **Gujarat** (drop Tamil Nadu and Karnataka).
- **Years:** core window 2018-01-01 → 2025-10-31. Keep 2025-11 → 2026-04 flagged as a separate regime. Walk-forward test months become May–Oct 2025.
- **Raw data location:** the archive sits in `csv/` and `parquet/` at the repo root. The path is configurable (`sources.kaggle.parquet_glob`). It could be moved to `data/raw/kaggle/` if you prefer; it's gitignored either way.

### Spec sections that still reflect the old plan (to tidy when convenient)
- §5 architecture box lists "data.gov.in / Agmarknet historical", not Kaggle/CEDA.
- §12 Phase 0 acceptance ("one real API call succeeds") isn't achievable while data.gov.in is down.
- §17 config starter has no `sources` block (the real `config/settings.yaml` does).
- §3 references "Section 6.3" for variety aggregation; that rule is in §7.4.

### Next (Phase 1, after the decisions above)
- Kaggle backfill → `data/raw/` partitions with `source='kaggle_archive'`; `load` into `raw.mandi_prices`; `ingest_log`.
- CEDA client once the token is in `.env`; cross-check report.
- Geocoding with cache and overrides.
