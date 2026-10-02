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

### Next: Phase 1 (done, see below)
- Kaggle backfill → `data/raw/` partitions with `source='kaggle_archive'`; `load` into `raw.mandi_prices`; `ingest_log`.
- CEDA client once the token is in `.env`; cross-check report.
- Geocoding with cache and overrides.

---

## Phase 1: Kaggle load, market aliases, geocoding (2026-10-02)

Adapted Phase 1 (per user): no API calls. "Ingestion" means loading the filtered Kaggle archive into Postgres, plus geocoding.

### Commands
```bash
python -m mandipulse load        # Parquet -> raw.mandi_prices (idempotent), logs to raw.ingest_log
python -m mandipulse reconcile   # raw counts vs Phase 0 profile -> reports/tables/phase1/load_reconciliation.csv
python -m mandipulse aliases     # -> data/reference/market_aliases.csv
python -m mandipulse geocode     # resumable; --retry not_found --retry district_centroid to redo
```

### 1. Load → `raw.mandi_prices`
- DuckDB filters the Parquet archive in place: 3 crops × 4 states, `arrival_date >= 2018-01-01`, exact commodity match, with `Onion Green` and `Sweet Potato` explicitly excluded. It writes a temporary CSV, which Postgres ingests with `COPY` (about 30–40 s).
- Added columns: `source = 'kaggle_archive'`, `source_file`, `period` (`main` up to 2025-10-31, `post_format_change` from 2025-11-01), `ingested_at`, `run_id`. Raw keeps rows exactly as received, including the archive's exact duplicates; staging will dedupe.
- **Idempotent:** each run deletes all rows of its `source` and inserts the fresh slice in one transaction. A failed run rolls back and leaves the previous load intact (tested).
- **Result:** 1826981 rows fetched, **0 rejected** (null date, names or modal price), 1826981 loaded. `main` = 1808839 rows (2018-01-01 → 2025-10-31); `post_format_change` = 18142 rows (2025-11-01 → 2026-04-20).
- **Re-run check:** the second run had `rows_replaced = 1826981`; the table still holds 1826981 rows, all from one `run_id`. Both runs show `success` in `raw.ingest_log`.
- **Reconciliation with the Phase 0 profile:** identical in every commodity × state × year cell (sum of absolute differences = **0**), so there are no differences to explain.

Rows in `raw.mandi_prices`. These equal the Phase 0 profile `07_scope_rows_by_year` for 2018 onward; 2026 covers Jan–Apr only.

| commodity | state | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 | total |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Onion | Gujarat | 5587 | 4846 | 3986 | 3953 | 5132 | 5682 | 6646 | 6037 | 627 | 42496 |
| Potato | Gujarat | 4621 | 5038 | 3337 | 3376 | 3795 | 4602 | 6503 | 6520 | 601 | 38393 |
| Tomato | Gujarat | 6606 | 6724 | 5436 | 4775 | 4803 | 5320 | 6951 | 7032 | 687 | 48334 |
| Onion | Madhya Pradesh | 7515 | 9644 | 6060 | 9267 | 13038 | 12165 | 8514 | 13219 | 1081 | 80503 |
| Potato | Madhya Pradesh | 7124 | 9296 | 5358 | 8599 | 11269 | 10068 | 2231 | 5281 | 510 | 59736 |
| Tomato | Madhya Pradesh | 7334 | 9957 | 5806 | 9043 | 11935 | 10121 | 1650 | 6327 | 430 | 62603 |
| Onion | Maharashtra | 13199 | 12885 | 12000 | 14677 | 14713 | 16266 | 16744 | 14270 | 1449 | 116203 |
| Potato | Maharashtra | 5581 | 4863 | 4485 | 6274 | 6273 | 7243 | 7221 | 6205 | 694 | 48839 |
| Tomato | Maharashtra | 10655 | 10055 | 9103 | 10682 | 10480 | 10869 | 10765 | 9508 | 923 | 83040 |
| Onion | Uttar Pradesh | 49232 | 47269 | 50538 | 50981 | 52508 | 51633 | 51538 | 47941 | 1448 | 403088 |
| Potato | Uttar Pradesh | 57623 | 58124 | 54228 | 54956 | 56978 | 56109 | 55332 | 50387 | 2294 | 446031 |
| Tomato | Uttar Pradesh | 45709 | 50297 | 49786 | 50885 | 50916 | 49421 | 51211 | 47902 | 1588 | 397715 |

### 2. Market identity → `data/reference/market_aliases.csv`
- 1056 raw market names → **633 canonical markets** (Gujarat 100 → 61, Madhya Pradesh 266 → 180, Maharashtra 235 → 137, Uttar Pradesh 455 → 255).
- Automatic (certain) rules, applied within one state × district:
  - `identity` (608 names): already canonical.
  - `apmc_suffix` (423): `X APMC` → `X` where `X` exists. HTML entities such as `&amp;` are unescaped first.
  - `apmc_suffix_only` (25): a new market seen only after the change. The suffix is removed and nothing is merged.
  - Brackets are kept, because they mark distinct sub-yards (`Pune (Pimpri)` is not `Pune (Manjri)`).
- **Not merged, flagged for review:** 65 raw names, which make up **43 canonical markets**. They carry `needs_review = True` plus `suggested_canonical` / `suggested_district`. The same list is in `reports/tables/phase1/market_alias_review.csv`.

#### Uncertain market matches: please review
The flags follow four patterns:
- **(a) Madhya Pradesh:** markets were reported as `X` until about 2023-12 and as `X (F&V)` from about 2024-09/10. So the MP Jan–Sep 2024 gap is a real gap *plus* a rename.
- **(b) Uttar Pradesh:** B/V spellings switched at the Nov-2025 change (`Visoli`→`Bisoli`, `Bahedi`→`Baheri`, `Vishalpur`→`Bishalpur`, `Wansi`→`Bansi`).
- **(c) Ghazipur:** four Ghazipur towns were filed under district *Hapur* until May 2024, which looks like a district mislabel in the old data.
- **(d) Likely false positives:** notably `Badnawar` ↔ `Manawar` (different towns) and `Vankaner` ↔ `Vankaner (Sub yard)`.

Tell me which to merge; accepted merges will be applied as manual entries in the alias file.

| State | District | Canonical (flagged) | Raw names | Rows | Active | Suggested match | Reason |
|---|---|---|---|---|---|---|---|
| Gujarat | Morbi | Vankaner | Vankaner APMC | 9 | 2026-03-12 → 2026-04-17 | Vankaner (Sub yard) | similar_name_no_overlap |
| Gujarat | Surat | Bardoli | Bardoli | 1 | 2019-03-15 → 2019-03-15 | Bardoli (Katod) | similar_name_no_overlap |
| Madhya Pradesh | Anupur | Anuppur (F&V) | Anuppur (F&V) APMC | 3 | 2026-02-23 → 2026-03-29 | Anuppur | similar_name_no_overlap |
| Madhya Pradesh | Badwani | Badwani (F&V) | Badwani (F&V) / Badwani (F&V) APMC | 665 | 2024-09-26 → 2026-04-19 | Badwani | similar_name_no_overlap |
| Madhya Pradesh | Badwani | Sendhwa (F&V) | Sendhwa (F&V) / Sendhwa (F&V) APMC / Sendhwa (F&amp;V) APMC | 460 | 2024-09-23 → 2026-04-19 | Sendhwa | similar_name_no_overlap |
| Madhya Pradesh | Betul | Betul (F&V) | Betul (F&V) | 90 | 2025-09-02 → 2025-11-04 | Betul | similar_name_no_overlap |
| Madhya Pradesh | Betul | Multai (F&V) | Multai (F&V) | 90 | 2025-08-28 → 2025-11-02 | Multai | similar_name_no_overlap |
| Madhya Pradesh | Chhatarpur | Chattarpur (F&V) | Chattarpur (F&V) / Chattarpur (F&V) APMC | 126 | 2024-10-03 → 2026-04-14 | Chhatarpur | similar_name_no_overlap |
| Madhya Pradesh | Chhindwara | Chhindwara | Chhindwara | 7 | 2024-12-17 → 2025-01-09 | Chhindwara (F&V) | similar_name_no_overlap |
| Madhya Pradesh | Chhindwara | Chindwara (F&V) | Chindwara (F&V) / Chindwara (F&V) APMC | 422 | 2024-10-11 → 2026-04-16 | Chhindwara (F&V) | similar_name_no_overlap |
| Madhya Pradesh | Damoh | Damoh | Damoh APMC | 1 | 2026-03-17 → 2026-03-17 | Damoh (F&V) | similar_name_no_overlap |
| Madhya Pradesh | Dewas | Hatpiplya (F&V) | Hatpiplya (F&V) APMC | 20 | 2026-02-05 → 2026-04-17 | Haatpipliya | similar_name_no_overlap |
| Madhya Pradesh | Dhar | Badnawar | Badnawar / Badnawar APMC | 973 | 2023-12-27 → 2026-04-13 | Manawar | similar_name_no_overlap |
| Madhya Pradesh | Dhar | Dhamnod (F&V) | Dhamnod (F&V) / Dhamnod (F&V) APMC | 678 | 2024-10-02 → 2026-03-29 | Dhamnod | similar_name_no_overlap |
| Madhya Pradesh | Dhar | Kukshi (F&V) | Kukshi (F&V) / Kukshi (F&V) APMC | 150 | 2025-09-01 → 2026-04-17 | Kukshi | similar_name_no_overlap |
| Madhya Pradesh | Dhar | Manawar (F&V) | Manawar (F&V) | 975 | 2024-09-26 → 2025-11-03 | Manawar | similar_name_no_overlap |
| Madhya Pradesh | Guna | Guna | Guna | 19 | 2025-05-31 → 2025-07-25 | Guna (F&V) | similar_name_no_overlap |
| Madhya Pradesh | Harda | Sirali (F&V) | Sirali (F&V) / Sirali (F&V) APMC | 133 | 2024-10-20 → 2026-04-10 | Sirali | similar_name_no_overlap |
| Madhya Pradesh | Harda | Timarni (F&V) | Timarni (F&V) / Timarni (F&V) APMC | 561 | 2024-09-23 → 2026-04-16 | Timarni | similar_name_no_overlap |
| Madhya Pradesh | Hoshangabad | Hoshangabad (F&V) | Hoshangabad (F&V) | 708 | 2024-10-03 → 2025-10-28 | Hoshangabad | similar_name_no_overlap |
| Madhya Pradesh | Hoshangabad | Itarsi (F&V) | Itarsi (F&V) | 165 | 2024-12-16 → 2025-10-30 | Itarsi | similar_name_no_overlap |
| Madhya Pradesh | Hoshangabad | Pipariya (F&V) | Pipariya (F&V) / Pipariya (F&V) APMC | 848 | 2024-10-06 → 2026-04-18 | Pipariya | similar_name_no_overlap |
| Madhya Pradesh | Indore | Mhow (F&V) | Mhow (F&V) | 962 | 2024-10-08 → 2025-11-04 | Mhow | similar_name_no_overlap |
| Madhya Pradesh | Indore | Sanwer (F&V) | Sanwer (F&V) / Sanwer (F&V) APMC | 187 | 2025-08-26 → 2026-04-17 | Sanwer | similar_name_no_overlap |
| Madhya Pradesh | Jhabua | Thandla (F&V) | Thandla (F&V) | 129 | 2025-08-29 → 2025-11-03 | Thandla | similar_name_no_overlap |
| Madhya Pradesh | Mandsaur | Shamgarh | Shamgarh / Shamgarh APMC | 425 | 2023-12-21 → 2026-04-18 | Shamgarh (F&V) | similar_name_no_overlap |
| Madhya Pradesh | Morena | Sabalgarh (F&V) | Sabalgarh (F&V) / Sabalgarh (F&V) APMC | 634 | 2024-10-14 → 2026-04-19 | Sabalgarh | similar_name_no_overlap |
| Madhya Pradesh | Rewa | Rewa (F&V) | Rewa (F&V) / Rewa (F&V) APMC | 257 | 2024-11-04 → 2026-04-18 | Rewa | similar_name_no_overlap |
| Madhya Pradesh | Sagar | Rehli (F&V) | Rehli (F&V) / Rehli (F&V) APMC | 80 | 2025-08-28 → 2026-04-16 | Rehli | similar_name_no_overlap |
| Madhya Pradesh | Seoni | Seoni (F&V) | Seoni (F&V) APMC | 30 | 2026-01-28 → 2026-04-17 | Seoni | similar_name_no_overlap |
| Madhya Pradesh | Shajapur | Akodiya | Akodiya | 295 | 2023-12-21 → 2024-07-26 | Akodia | similar_name_no_overlap |
| Madhya Pradesh | Shajapur | Akodiya (F&V) | Akodiya (F&V) | 17 | 2024-09-30 → 2025-11-03 | Akodia | similar_name_no_overlap |
| Madhya Pradesh | Shajapur | Shajapur | Shajapur / Shajapur APMC | 1206 | 2024-07-01 → 2026-04-18 | Sajapur | similar_name_no_overlap |
| Madhya Pradesh | Sheopur | Sheopurkalan (F&V) | Sheopurkalan (F&V) / Sheopurkalan (F&V) APMC | 287 | 2024-10-08 → 2026-04-14 | Syopurkalan (F&V) | similar_name_no_overlap |
| Madhya Pradesh | Singroli | Singroli (F&V) | Singroli (F&V) | 71 | 2025-05-13 → 2025-10-28 | Singroli | similar_name_no_overlap |
| Uttar Pradesh | Badaun | Bisoli | Bisoli APMC | 50 | 2025-12-03 → 2026-04-20 | Visoli | similar_name_no_overlap |
| Uttar Pradesh | Bareilly | Baheri | Baheri APMC | 1 | 2026-02-27 → 2026-02-27 | Bahedi | similar_name_no_overlap |
| Uttar Pradesh | Ghazipur | Gazipur | Gazipur / Gazipur APMC | 1252 | 2024-05-01 → 2026-01-13 | Gazipur (district Hapur) | same_name_other_district |
| Uttar Pradesh | Ghazipur | Jamanian | Jamanian / Jamanian APMC | 25 | 2025-06-21 → 2026-04-05 | Jamanian (district Hapur) | same_name_other_district |
| Uttar Pradesh | Ghazipur | Jangipura | Jangipura / Jangipura APMC | 38 | 2025-02-28 → 2026-04-17 | Jangipura (district Hapur) | same_name_other_district |
| Uttar Pradesh | Ghazipur | Yusufpur | Yusufpur / Yusufpur APMC | 60 | 2024-05-09 → 2026-04-08 | Yusufpur (district Hapur) | same_name_other_district |
| Uttar Pradesh | Pillibhit | Bishalpur | Bishalpur APMC | 19 | 2025-12-11 → 2026-01-13 | Vishalpur | similar_name_no_overlap |
| Uttar Pradesh | Siddharth Nagar | Bansi | Bansi APMC | 15 | 2025-12-16 → 2026-04-17 | Wansi | similar_name_no_overlap |

### 3. Geocoding → `data/reference/market_geo.csv`
- Nominatim at 1 request/s, with a resumable cache: each result is appended immediately and cached markets are skipped.
- Attempts per market, in order:
  1. The locality in brackets (`Pune (Pimpri)` → Pimpri).
  2. The name before the brackets.
  3. The same queries without the district, accepted only within 100 km of the district centroid.
  4. Fallback: the district centroid.
- A hit counts only if Nominatim's state matches and it lies within 100 km (`geo.max_km_from_district`) of the district centroid.
- District centroids are cached in `data/reference/district_geo.csv` (165 districts, all found). 11 data spellings differ from OSM; they are mapped in the hand-curated `data/reference/district_osm_names.csv` (e.g. `Badwani`→Barwani, `Pillibhit`→Pilibhit, `Kannuj`→Kannauj, `Chattrapati Sambhajinagar`→Chhatrapati Sambhajinagar).
- `data/reference/market_geo_overrides.csv` (empty for now) wins over everything (`geo_precision = 'manual'`).
- **Coverage: 633 of 633 canonical markets (100%) have coordinates** (`reports/tables/phase1/geocode_coverage.csv`):

| geo_precision | markets | % |
|---|---|---|
| market | 478 | 75.5 |
| district_centroid | 155 | 24.5 |
| not_found | 0 | 0 |

- By state (market / district_centroid): Gujarat 55 / 6, Madhya Pradesh 147 / 33, Maharashtra 109 / 28, Uttar Pradesh 167 / 88.
- Market-level hits lie a median 23 km (max 98.5 km) from their district centroid.
- Run history: pass 1 gave 441 market / 159 centroid / 33 not_found. All 33 failures were in 11 districts with non-OSM spellings. After adding the OSM names and the district-less query, a retry of `not_found` and `district_centroid` gave the final numbers above.
- Caveats:
  - "Market" precision is really **town/locality** level, because OSM resolves the town, not the yard. For example, `Betul` and `Betul (F&V)`, or `Pune` and `Pune (Khadiki)`, share coordinates, so Phase 3's pair analysis must expect 0 km pairs.
  - Uttar Pradesh has the most centroid fallbacks (88), so UP distances are coarser.

### 4. data.gov.in client (stub)
`src/mandipulse/ingest/datagov_client.py` implements the spec §6.3 pagination rule:
- It requests the next offset until a page comes back **empty**.
- The offset advances by the rows **actually received**, and the rows received are logged per page.
- It retries on timeouts, 429 and 5xx, and has a `max_pages` guard.

It is unit-tested with `requests_mock` and never called: `sources.datagov.enabled` is false, and `client_from_settings` refuses to build a client while it is disabled.

### 5. Tests & lint
`pytest`: **32 passed**.
- `test_load`: scope filter, periods, rejects, idempotency, and failed-run rollback, against Postgres in a throwaway schema.
- `test_market_aliases`: the alias rules.
- `test_distance`: haversine within 1% of the WGS-84 geodesic.
- `test_datagov_client`: pagination.
- `test_geocode`: precision rules, plus crash and resume with a fake geocoder.
- `test_config`: config smoke tests.

`ruff check` and `ruff format --check` are clean. CI now starts a Postgres service so the load tests run there too.

### Deviations / problems
- **The Nominatim contact email is sent as the `email=` parameter, not in the User-Agent.** A User-Agent containing the email (`mandi-pulse-portfolio (contact: <email>)`) was refused with HTTP 403 "Access denied". A plain `MandiPulse/0.1` User-Agent with the email in Nominatim's documented `email=` parameter works. geopy cannot send `email=`, so geocoding uses a small `requests` client with its own 1 request/s limiter, and it stops on HTTP 403 instead of retrying.
- **No raw Parquet landing partitions** (spec §4/§6.5 `data/raw/date=…`). The Kaggle Parquet in `data/raw/kaggle/` is itself the immutable landing zone; daily partitions will come with the data.gov.in feed.
- **`schemas.py` (pydantic record model) is not written yet.** It belongs with the live data.gov.in/CEDA clients. Kaggle rows are validated in SQL instead: rows with a null date, names or modal price are rejected and counted.
- **District names are kept as in the data** (the old names). There's no district aliasing beyond the geocoding map.

### Next: Phase 2 (after your alias review)
dbt seeds (aliases, including your accepted merges), staging (dedupe, `market_clean` via aliases), `int_price_flags`, `int_daily_prices`, the star schema, and dbt tests.
