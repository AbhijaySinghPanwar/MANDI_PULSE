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

### Phase 0 acceptance
- **Postgres up:** `docker compose up -d` → container `mandipulse-postgres` healthy. Reached from Python via SQLAlchemy using `DATABASE_URL` from `.env`: `PostgreSQL 16.15 (Debian 16.15-1.pgdg13+2)`, db `mandipulse`, user `mandipulse` (2026-10-02). (Docker Desktop wasn't running at first; it was launched from its per-user install.)
- **No data.gov.in call** (site unreachable). This acceptance item is waived by the user; the resource ID stays unverified.
- **No CEDA call** (token not yet provided).
- `docs/DATA_SOURCES.md` documents the chosen sources and caveats.

### Key findings (details and numbers in docs/DATA_SOURCES.md)
1. 75984017 rows, 2001-01-10 → 2026-04-21. CSV and Parquet match exactly. The **archive ends 5½ months before today**.
2. Commodity and state spellings match the spec exactly. Exclude the look-alikes `Onion Green` and `Sweet Potato`.
3. **Source change in Nov 2025:** markets renamed `X` → `X APMC`, and reporting density falls from ~28–30 to ~4–9 days/month. It had already been thinning since Jul 2025.
4. **Tamil Nadu:** almost no Tomato/Onion/Potato data from 2013 to mid-2024. Since then about 92% of rows come from Uzhavar Sandhai (near-retail) markets, and the other markets often enter prices in ₹/kg.
5. **Karnataka and Madhya Pradesh** look complete at state level but are thin at market level (median 34–52 report days per series over 2023-11 → 2025-10; Karnataka tomato 152). MP has a hole in Jan–Sep 2024.
6. Quality: zero min/max placeholders are 2.4% overall but <0.5% a year from 2018. In scope: 136 exact duplicates (none conflicting), no null or zero modal prices.

### Decisions (made by the user, 2026-10-02, applied)
- **States:** Maharashtra, Madhya Pradesh, Uttar Pradesh, Gujarat. Tamil Nadu dropped (Uzhavar Sandhai retail-like prices, per-kg units, no 2013–mid-2024 history). Karnataka dropped (thin market-level data). Reasons recorded in `docs/DATA_SOURCES.md` §4 and spec §3.
- **Years:** load from 2018-01-01. `period = 'main'` for 2018-01-01 → 2025-10-31, `'post_format_change'` from 2025-11-01. ML walk-forward test months May–Oct 2025 (spec §9.1, `ml.walk_forward_test_months`).
- **Flagged:** Madhya Pradesh reporting gap Jan–Sep 2024 (`docs/DATA_SOURCES.md` §1.5).
- **Crops:** Tomato, Onion, Potato. `Onion Green` and `Sweet Potato` are explicitly excluded (`scope.exclude_commodities`).
- **Raw data:** Parquet moved to `data/raw/kaggle/`; config updated. **The CSV copy in `csv/` is not used anywhere and is safe for you to delete** (CSV/Parquet parity was verified: both have 75984017 rows and the same date range).
- **data.gov.in pagination rule** added to spec §6.3, replacing the TODO.
- Phase 0 profile re-run over the 6 states (original 4 + UP, GJ), so the docs cover both the dropped and the added states. New query `23_scope_quality_by_year` shows UP's zero-price placeholders are pre-2018 (34–55% of rows a year in 2008–2016, 1.83% in 2018, 0.01% in 2025).

### Spec sections that still reflect the old plan (to tidy when convenient)
- §5 architecture box lists "data.gov.in / Agmarknet historical", not Kaggle/CEDA.
- §12 Phase 0 acceptance ("one real API call succeeds") isn't achievable while data.gov.in is down.
- §3 references "Section 6.3" for variety aggregation; that rule is in §7.4.

### Next: Phase 1
- Kaggle backfill → `data/raw/` partitions with `source='kaggle_archive'`; `load` into `raw.mandi_prices`; `ingest_log`.
- CEDA client once the token is in `.env`; cross-check report.
- Geocoding with cache and overrides.
