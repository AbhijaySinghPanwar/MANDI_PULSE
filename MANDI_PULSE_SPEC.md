# Mandi Pulse — Project Specification & Build Plan

> **"Google Flights for farmers' vegetable prices."**
> An end-to-end data analytics + ML project that tells a farmer (or trader, FPO, or policy analyst) **which mandi gives the best net price for their crop this week**, warns them **before prices crash**, and shows **which districts are structurally stuck with bad prices**.

**Author:** Abhijay Singh Panwar
**Intended builder:** Claude Code (working phase by phase from this file)
**Primary audience of the output:** Data Analyst / Analytics Engineer recruiters

---

## 0. How to use this file (instructions for Claude Code)

1. Read this entire file before writing any code.
2. Work **one phase at a time** (Section 12). Do not start a phase until the previous phase's **acceptance criteria** are met.
3. After each phase:
   - run the tests and dbt tests,
   - update `PROGRESS.md` (what was done, what's left, any decisions or deviations),
   - make a git commit with a clear message (`phase-2: dbt staging models + tests`).
4. **Never fabricate data, prices, distances, or results.** Every number that appears in the README, insights brief, or dashboard must come from a query or notebook saved in the repo. If a data source fails, **stop and report**; do not substitute synthetic data silently. Synthetic data is allowed **only** for unit-test fixtures, and must live in `tests/fixtures/`.
5. If an external API or website behaves differently from what this spec assumes (resource IDs, field names, rate limits), **verify first, adapt the code, and record the change in `PROGRESS.md` and `docs/DATA_SOURCES.md`.**
6. Prefer simple, readable code over clever code. This is a portfolio project: a recruiter should be able to read any file and understand it.
7. Ask the user before adding any heavy dependency not listed in Section 4.
8. Claude Code **cannot build the Power BI `.pbix` file**. Instead, prepare the data exports and the dashboard spec (Section 10) so the user can build it in Power BI Desktop.

---

## 1. Plain-English summary (the 30-second pitch)

Every day, the government publishes the price of vegetables at thousands of mandis (wholesale markets). The same crop on the same day can sell for very different prices at two mandis only 50 km apart. Farmers usually sell at the nearest mandi because they can't see the bigger picture.

Mandi Pulse:
1. **Collects** daily mandi prices automatically.
2. **Cleans** them (the raw data is messy: inconsistent names, bad entries, gaps).
3. **Computes** the *net* price at nearby mandis after subtracting transport cost.
4. **Forecasts** prices 7 days ahead and **flags likely price crashes** using ML.
5. **Shows** it all in a Power BI dashboard (for analysts) and a Streamlit app (for an end user).
6. **Summarises** the findings in a one-page insights brief, like a consultant's memo.

**Analogy:** Flight-price trackers compare the same flight across dates and routes. We compare the same crop across mandis and dates, then subtract the "travel cost" to see if the better deal is actually worth it.

---

## 2. Problem statement & key questions

**Problem:** Price information exists but isn't usable. Farmers lose income by selling at the wrong place or time, especially for perishables like tomato that can't be stored.

**Questions the project must answer (with numbers):**

| # | Question | Where it's answered |
|---|---|---|
| Q1 | How big is the price gap between nearby mandis (≤100 km) for the same crop on the same day? | `mart_price_spread` + dashboard |
| Q2 | After transport costs, how often is selling at a farther mandi actually profitable, and by how much (₹/quintal)? | `mart_net_price_opportunities` |
| Q3 | Which months and crops crash predictably? How early do warning signs appear? | `mart_seasonality` + crash model |
| Q4 | Which districts are "price-trapped" (few mandis nearby, consistently below-average prices)? | `mart_district_access` + clustering |
| Q5 | How does volatility differ between perishables (tomato) and storables (onion, potato)? | `mart_volatility` |
| Q6 (ML) | Can we forecast the 7-day-ahead modal price better than simple baselines? | Forecast model report |
| Q7 (ML) | Can we warn of a price crash 14 days in advance with useful precision? | Crash model report |

---

## 3. Scope (keep it finishable)

**In scope (v1):**
- **Commodities:** Tomato, Onion, Potato (perishable vs storable contrast). Matched by exact name; the look-alikes **`Onion Green` and `Sweet Potato` are explicitly excluded**. Configurable in `config/settings.yaml` so more can be added later.
- **States:** **Maharashtra, Madhya Pradesh, Uttar Pradesh, Gujarat** (decided after Phase 0 profiling; configurable). They form one contiguous block, which helps the nearby-mandi analysis.
  - *Tamil Nadu dropped:* since 2024 about 92% of its rows come from Uzhavar Sandhai farmer-to-consumer markets with retail-like prices (about 2× wholesale); its other markets often enter prices per kg instead of per quintal; and there is no history from 2013 to mid-2024.
  - *Karnataka dropped:* thin data at market level. Only 2–24 market series per crop report on ≥ 180 days a year, falling to 2–6 in 2025.
  - *Caveat:* Madhya Pradesh has a reporting gap in Jan–Sep 2024.
  - Evidence: `docs/DATA_SOURCES.md` sections 1.5–1.8 and 4.
- **History:** load from **2018-01-01**. Every row carries a `period` tag: `main` = 2018-01-01 → 2025-10-31 (the analysis window) and `post_format_change` = 2025-11-01 onward (kept, but after the Nov-2025 source change; see 6.1).
- **Granularity:** Daily, per market × commodity (varieties aggregated, see Section 7.4).

**Out of scope (v1):** real-time mobile app, road-network routing, farmer-level personal data, any paid APIs.

**Stretch goals (only after v1 is done):** more commodities and states, rainfall features, cloud deployment with a scheduled pipeline, MLflow tracking.

---

## 4. Tech stack

| Layer | Tool | Why |
|---|---|---|
| Language | Python 3.11 | Core skill |
| Ingestion | `requests`, `tenacity` (retries), `pydantic` (schema validation) | Robust API client |
| Raw storage | Parquet files in `data/raw/` (partitioned by date) | Cheap, replayable "landing zone" |
| Warehouse | **PostgreSQL 16** (via `docker-compose`) | Power BI has a native connector; real SQL skills |
| Transformations | **dbt-core + dbt-postgres** | Industry-standard analytics engineering; built-in tests |
| Analysis | Pandas, SQL, Jupyter | Exploration and charts |
| Geocoding | `geopy` with OpenStreetMap Nominatim (rate-limited, cached) | Free mandi coordinates |
| ML | **scikit-learn, LightGBM, SHAP** | Strong tabular models, explainable |
| App | **Streamlit** + `pydeck` or `folium` | End-user "best mandi" tool |
| BI | **Power BI Desktop** (built by user from spec) | Analyst dashboard |
| Quality | `pytest`, `ruff`, dbt tests | Professional hygiene |
| CI | GitHub Actions | Lint + tests on every push |
| Config | `config/settings.yaml` + `.env` (secrets) | No hard-coded values |

**Fallback:** If Docker is a problem on the user's machine, the code must also run with a local PostgreSQL install via the same `DATABASE_URL`. Use SQLAlchemy for all Python DB access so the connection string is the only thing that changes.

---

## 5. System architecture

```
                         ┌──────────────────────────────┐
                         │   EXTERNAL DATA SOURCES      │
                         │ • data.gov.in mandi API      │
                         │ • Agmarknet historical data  │
                         │ • OSM Nominatim (geocoding)  │
                         │ • (stretch) IMD rainfall     │
                         └──────────────┬───────────────┘
                                        │
                 ┌──────────────────────▼──────────────────────┐
  LAYER 1        │ INGESTION  (src/mandipulse/ingest/)         │
  "Collect"      │ • API client with retries + pagination      │
                 │ • Historical backfill job                    │
                 │ • Daily incremental job                      │
                 │ • Writes raw Parquet → data/raw/date=YYYY-MM-DD/
                 └──────────────────────┬──────────────────────┘
                                        │ load
                 ┌──────────────────────▼──────────────────────┐
  LAYER 2        │ POSTGRES  schema: raw                        │
  "Store"        │ • raw.mandi_prices (append-only)             │
                 │ • raw.market_geo (geocoded mandis)           │
                 │ • raw.ingest_log (run metadata)              │
                 └──────────────────────┬──────────────────────┘
                                        │ dbt
                 ┌──────────────────────▼──────────────────────┐
  LAYER 3        │ dbt TRANSFORMATIONS                          │
  "Clean &       │ staging  → clean names, units, types, dedupe │
   model"        │ intermediate → daily series, distances, flags│
                 │ marts    → star schema + analysis marts      │
                 │ tests    → not_null, unique, custom checks   │
                 └───────┬───────────────┬──────────────┬──────┘
                         │               │              │
           ┌─────────────▼───┐   ┌───────▼──────┐  ┌────▼──────────────┐
  LAYER 4  │ ML (src/ml/)    │   │ ANALYSIS     │  │ EXPORTS           │
  "Learn & │ • 7-day forecast│   │ notebooks +  │  │ CSV/Parquet for   │
   analyse"│ • crash warning │   │ saved SQL    │  │ Power BI          │
           │ • mandi clusters│   │ queries      │  │                   │
           │ → writes ml.*   │   │              │  │                   │
           └────────┬────────┘   └──────┬───────┘  └────┬──────────────┘
                    │                   │               │
           ┌────────▼────────┐  ┌───────▼───────┐  ┌────▼──────────────┐
  LAYER 5  │ STREAMLIT APP   │  │ INSIGHTS BRIEF│  │ POWER BI          │
  "Serve"  │ "Best mandi     │  │ (1-page memo) │  │ DASHBOARD         │
           │  this week"     │  │               │  │ (user-built)      │
           └─────────────────┘  └───────────────┘  └───────────────────┘
```

**Design principle (analogy):** Think of it like a restaurant kitchen. Raw ingredients (raw schema) are never thrown away. Prep (staging) cleans them. Cooking (marts) combines them into dishes. The dashboard and app are the plates served to customers. If a dish tastes wrong, you can always go back to the raw ingredients and re-cook.

---

## 6. Data sources & ingestion

**Source order (revised in Phase 0, 2026-10-02):** Kaggle archive (history) → CEDA (cross-check + arrivals) → data.gov.in API (daily, later). All three derive from Agmarknet. Every source writes the **same raw schema** plus a `source` column (`kaggle_archive`, `ceda`, `datagov_daily`) so downstream code doesn't care where a row came from. Prices are in **₹ per quintal** (100 kg) in every source. Keep this unit everywhere and label it on every chart. Full profiling and caveats: `docs/DATA_SOURCES.md`.

### 6.1 Primary (history): Kaggle archive

- Dataset: *"Daily Market Prices of Commodity India (2001-2026)"* by khandelwalmanas on Kaggle, **GODL-India** licence (attribute in README).
- Downloaded manually. The Parquet files live in `data/raw/kaggle/{YYYY}.parquet` (path in `sources.kaggle.parquet_glob`). A CSV copy with the same content is redundant. **Both are gitignored and must never be committed.** Use the Parquet files.
- About 76M rows, 2001-01-10 → 2026-04-21. Columns: `State, District, Market, Commodity, Variety, Grade, Arrival_Date, Min_Price, Max_Price, Modal_Price, Commodity_Code`. There is **no arrival-quantity column**.
- **Never load the full archive into pandas.** Query it in place with DuckDB (or Polars lazy mode); only small filtered results come into memory. Read with `union_by_name=true` and cast prices to DOUBLE (types differ between yearly files).
- Known caveats (details in `docs/DATA_SOURCES.md`):
  - From late Nov 2025 market names gain an ` APMC` suffix and reporting density collapses. Stripping "APMC" into `market_clean` (7.2) is mandatory. Treat 2025-11 onward as a separate regime.
  - The archive ends 2026-04-21; later dates must come from 6.2 or 6.3.
  - `2026.parquet` contains some rows dated 2025-12-30; dedupe across files.
- The `backfill` job reads this archive for the configured scope and writes raw Parquet partitions with `source = 'kaggle_archive'`.

### 6.2 Secondary (cross-check + arrivals): CEDA Agri Market Data

- Publisher: Centre for Economic Data and Analysis (CEDA), Ashoka University. Agmarknet-derived and harmonised.
- Uses: (a) cross-check Kaggle prices on overlapping dates and report the agreement rate; (b) **arrival quantities**, which the Kaggle archive lacks (useful as a real supply feature in 9.1/9.2, replacing the "markets reporting" proxy); (c) possibly fill 2025-11 → present.
- Auth: API token in `.env` as `CEDA_API_TOKEN`. Verify endpoints, field names, rate limits, and licence before writing code against them, and record them in `docs/DATA_SOURCES.md`.
- Rows written with `source = 'ceda'`. When CEDA and Kaggle disagree on the same key, keep both in raw; staging picks the precedence documented in `docs/DATA_SOURCES.md`.

### 6.3 Daily feed (later): data.gov.in mandi API

- Dataset: *"Current Daily Price of Various Commodities from Various Markets (Mandi)"* on data.gov.in (Agmarknet).
- Resource ID at time of writing: `9ef84268-d588-465a-a308-a864a43d0070` (**unverified**: data.gov.in was unreachable in Phase 0).
- Endpoint pattern:
  `https://api.data.gov.in/resource/{RESOURCE_ID}?api-key={KEY}&format=json&limit={N}&offset={M}&filters[state]={STATE}&filters[commodity]={COMMODITY}`
- Requires a free API key (`DATA_GOV_API_KEY` in `.env`).
- Expected fields: `state, district, market, commodity, variety, grade, arrival_date, min_price, max_price, modal_price`.
- This resource only exposes *recent* records, so it is the incremental feed, not a history source. Rows written with `source = 'datagov_daily'`.
- **Pagination rule:** When paginating the data.gov.in API, keep requesting the next offset until a page comes back empty. Never assume the server honours the requested limit; it may return fewer rows per page (e.g., 10 instead of 1000). Log the actual rows received per page.
  - Implementation consequence: the next offset advances by the number of rows **actually received**, not by the requested limit. Otherwise rows are skipped whenever the server returns short pages.

### 6.4 Mandi geolocation

- Build a unique list of canonical `(state, district, market)` from `data/reference/market_aliases.csv`. The aliases map every raw name to one canonical name per (state, district): ` APMC` suffix stripped and HTML entities unescaped. Doubtful matches are flagged for review, never merged automatically.
- Geocode with Nominatim: query `"{market}, {district}, {state}, India"` (bracketed locality first, then the name before the brackets), then the same without the district, falling back to the district centroid if not found. A hit is accepted only if it is in the right state and within `geo.max_km_from_district` (100 km) of the district centroid. District spellings that differ from OSM are mapped in `data/reference/district_osm_names.csv`.
- **Rate limit: 1 request/second**, with a plain application `User-Agent`. The contact email (`NOMINATIM_EMAIL` in `.env`) is sent as Nominatim's `email=` parameter, because a User-Agent containing the email was refused with HTTP 403. Cache results in `data/reference/market_geo.csv` (district centroids in `district_geo.csv`), so geocoding never repeats and an interrupted run resumes.
- Store `geo_precision` = `market` | `district_centroid` | `manual` | `not_found`. "market" is effectively town/locality level.
- Provide `data/reference/market_geo_overrides.csv` for manual fixes (empty at first). Overrides win.

### 6.5 Ingestion requirements

- Pagination until no more records; retries with exponential backoff (`tenacity`); timeouts.
- Validate each record with a `pydantic` model; log and count rejects. Never crash the whole run on one bad row.
- Raw write is **idempotent**: re-running the same date replaces that date's partition rather than duplicating it.
- Every run writes a row to `raw.ingest_log`: run_id, source, started_at, finished_at, rows_fetched, rows_rejected, status, error.
- CLI entrypoints (use `typer`):
  ```
  python -m mandipulse ingest daily
  python -m mandipulse ingest backfill --start 2023-01-01 --end 2025-12-31
  python -m mandipulse geocode
  python -m mandipulse load        # parquet → postgres raw
  python -m mandipulse pipeline    # ingest daily → load → dbt run/test → ml score → export
  ```

---

## 7. Data model (dbt)

### 7.1 Schemas

- `raw` — exactly as received (plus `source`, `ingested_at`).
- `staging` — cleaned, typed, one model per source (`stg_mandi_prices`, `stg_market_geo`).
- `intermediate` — reusable logic (`int_daily_prices`, `int_market_pairs`, `int_price_flags`).
- `marts` — star schema + analysis marts consumed by Power BI, ML, and the app.
- `ml` — written by Python ML jobs (forecasts, crash scores, clusters).

### 7.2 Staging rules (`stg_mandi_prices`)

- Trim, collapse whitespace, title-case names. Strip suffixes like "APMC", "(F&V)", "Market Yard" into a `market_clean` column, but keep the original too.
- Map name variants via `seeds/market_aliases.csv` and `seeds/commodity_aliases.csv` (dbt seeds).
- Cast `arrival_date` to DATE (handle `dd/mm/yyyy`); cast prices to NUMERIC.
- **Deduplicate** on `(arrival_date, state, district, market_clean, commodity, variety, grade)`, keeping the latest `ingested_at`.

### 7.3 Data quality flags (`int_price_flags`)

Flag rows (don't delete them; filter them in marts):
- `flag_nonpositive`: any price ≤ 0
- `flag_order`: not (min ≤ modal ≤ max)
- `flag_outlier`: |log(modal) − log(rolling 30-day median for that market × commodity)| > ln(3) (i.e., more than 3× off). Tune and document.
  - *Tuned in Phase 2:* the rolling median uses the 30 days **before** the report (same day excluded, ≥ 5 prior report days required). A row is an outlier only if it is also > 3× off the **same-day median of its state's markets** (when ≥ 3 markets report that day). The own-history rule alone flagged 24% of tomato rows in July 2023 (the genuine nationwide spike), which would delete the very crashes and spikes the ML layer must learn. The spec-only result is kept as `flag_outlier_temporal`; `quality.outlier_rule: temporal` restores it.
- `flag_unit_suspect`: price < ₹50/quintal or > ₹20,000/quintal for TOP crops (configurable bounds; likely a per-kg or per-tonne entry error)

`is_valid = NOT any flag`. Report the % of rows flagged per flag in the README. This is a talking point ("I found and handled X% bad records").

### 7.4 Daily series (`int_daily_prices`)

- Aggregate varieties and grades to **one price per market × commodity × day**: the median `modal_price` across valid rows, plus `n_varieties` and min/max.
- Markets don't report every day. Do **not** forward-fill in dbt; keep gaps explicit. (The ML layer handles gaps.)

### 7.5 Star schema (marts)

```
dim_date        (date_key, date, day_of_week, week, month, month_name, quarter, year, is_weekend)
dim_commodity   (commodity_key, commodity, category ['perishable'|'storable'])
dim_market      (market_key, market_clean, district, state, latitude, longitude, geo_precision)
fact_daily_price(date_key, market_key, commodity_key, modal_price, min_price, max_price,
                 n_varieties, source)
```

### 7.6 Analysis marts

**`int_market_pairs`**: all pairs of markets within `max_pair_km` (default 150 km), with:
- `haversine_km`
- `road_km_est = haversine_km × road_factor` (default 1.3; documented assumption)

**`mart_price_spread`** (Q1): per date × commodity × pair (≤100 km road est.): `price_home`, `price_dest`, `abs_gap`, `pct_gap`. Also a daily rollup per commodity with median/P90 gap.

**`mart_net_price_opportunities`** (Q2):
```
transport_cost = road_km_est × cost_per_qtl_km + fixed_cost_per_qtl
net_price_dest = price_dest − transport_cost
gain           = net_price_dest − price_home
is_opportunity = gain ≥ min_gain_abs AND gain / price_home ≥ min_gain_pct
```
Compute for **three cost scenarios** (low, mid, high) from config, so results are shown as a range rather than one fragile number. Defaults (assumptions to document and let the user tune):

| Param | Low | Mid | High |
|---|---|---|---|
| `cost_per_qtl_km` (₹) | 1.0 | 1.5 | 2.5 |
| `fixed_cost_per_qtl` (₹, handling + fees) | 30 | 50 | 80 |
| `min_gain_abs` (₹/qtl) | 100 | 100 | 100 |
| `min_gain_pct` | 5% | 5% | 5% |

**`mart_seasonality`** (Q3): per commodity × state × month: median price, price index vs. annual median, crash frequency (from the crash label definition in 9.2).

**`mart_volatility`** (Q5): per commodity × market: coefficient of variation, average absolute daily % change, max drawdown within the year.

**`mart_district_access`** (Q4): per district × commodity:
- `n_markets_within_50km`
- `avg_price_index` = district's average price / state's average price on the same days
- `opportunity_rate` = share of days with ≥1 profitable opportunity within 100 km
- `is_price_trapped` = `n_markets_within_50km ≤ 2 AND avg_price_index < 0.9` (document the thresholds)

### 7.7 dbt tests (required)

- `unique` + `not_null` on all keys; `relationships` from facts to dims.
- `accepted_values` for `commodity` (from config) and `category`.
- Custom generic test: `modal_between_min_max` on `fact_daily_price`.
- Custom singular test: no market appears with more than one coordinate pair.
- Source freshness check on `raw.mandi_prices` (warn if > 2 days old). *Disabled while the only source is the static Kaggle archive (ends 2026-04-21); re-enable with the daily data.gov.in feed.*

---

## 8. Analysis layer

- `notebooks/01_eda.ipynb`: coverage (markets per day, gaps), distributions, flag rates.
- `notebooks/02_spreads_and_opportunities.ipynb`: answers Q1 and Q2 with charts.
- `notebooks/03_seasonality_volatility.ipynb`: answers Q3 and Q5.
- `notebooks/04_price_trapped_districts.ipynb`: answers Q4.
- Every number used in the insights brief must come from a `.sql` file in `analysis/queries/` (named like `q2_opportunity_rate_by_state.sql`), run via a small helper that saves results to `reports/tables/`.
- Charts saved as PNG to `reports/figures/` for the README.

---

## 9. ML layer

The ML parts are deliberately **practical and explainable**. The goal is a model a business user would trust, not a leaderboard score.

**Analogy:** The forecast model is like a weather forecast for prices. The crash model is like a cyclone warning: it doesn't need to predict the exact price, just raise an alarm early enough to act.

### 9.1 Model A — 7-day price forecast (regression)

- **Target:** median modal price per market × commodity, **7 days ahead**. Model `log(price)`, convert back for reporting.
- **Series prep:** reindex each series to daily; forward-fill gaps of **≤ 3 days**, add `days_since_last_report`; drop series with < 180 valid days.
- **Features** (all computed using only past data; **no leakage**):
  - lags: 1, 3, 7, 14, 28 days
  - rolling mean/std/min/max: 7, 14, 30 days
  - momentum: price / rolling_30_mean
  - same-period-last-year ratio (if ≥ 1 year history)
  - state-level median price lags (the "regional mood")
  - number of markets reporting that commodity in the state (supply proxy)
  - calendar: day of week, month, week of year
  - categorical: commodity, state, market (LightGBM native categorical)
  - (stretch) rainfall in the past 7/30 days
- **Model:** one **global LightGBM** regressor across all series. Also train **quantile models** (α = 0.1 and 0.9) for a prediction band.
- **Baselines (must be beaten, or the result reported honestly):**
  1. Naive: last observed price
  2. Seasonal naive: price 7 days ago
  3. 7-day moving average
- **Validation:** walk-forward (expanding window). Test months are **May–Oct 2025**, the last 6 months of the `main` period (`ml.walk_forward_test_months` in config). For each test month: train on everything before the month, predict each day of that month. Never shuffle. `post_format_change` rows are not used for evaluation.
- **Metrics:** MAE (₹/qtl), MAPE, sMAPE, overall and per commodity; band coverage (% of actuals inside the p10–p90 band, target ≈ 80%).
- **Success criterion:** ≥ 10% lower MAE than the best baseline on the walk-forward test. If not met, keep the model and write up why (this is still a valid, honest result).

### 9.2 Model B — Price crash early warning (classification)

- **Label definition:** for market × commodity on day *t*,
  `crash = 1` if `min(price[t+1 … t+14]) < 0.7 × median(price[t−29 … t])`.
  (I.e., the price drops more than 30% below its recent normal within two weeks. Thresholds in config.)
- **Features:** the same as Model A, plus 7-day and 14-day price slopes, the state-level share of markets already falling, and seasonality (historical crash rate for that commodity × month, computed on training data only).
- **Model:** LightGBM classifier with `class_weight` / `scale_pos_weight` for imbalance. Logistic regression as a baseline.
- **Validation:** time-based split (same walk-forward as 9.1).
- **Metrics:** PR-AUC (main), precision, recall, F1 at the chosen threshold. Choose the threshold for **precision ≥ 0.6** where possible (false alarms erode trust) and report the recall you get there. Also report the **average lead time** of correct warnings.
- **Baseline to beat:** "seasonal rule": alert if the historical crash rate for that commodity × month exceeds X%.

### 9.3 Model C — Market segmentation (clustering)

- Per market × commodity, compute: price CV, average price index vs state, reporting frequency, seasonal amplitude, crash frequency, `n_markets_within_50km`.
- Standardise; KMeans with k ∈ {3,4,5,6}; choose by silhouette score + interpretability.
- **Give each cluster a plain-English name** (e.g., "Stable & fair", "Volatile hub", "Chronically under-priced", "Thin & erratic"), based on its centroid.
- Use the clusters to support Q4 (price-trapped districts) in the dashboard.

### 9.4 Explainability

- SHAP summary plots for Models A and B → `reports/figures/shap_*.png`.
- In the README, explain the top 5 drivers in plain language (e.g., "When the state-wide price is already falling, local crashes become much more likely").

### 9.5 ML engineering

- Code in `src/mandipulse/ml/`: `features.py`, `train_forecast.py`, `train_crash.py`, `cluster.py`, `score.py`, `evaluate.py`.
- Saved artifacts: `models/{model_name}/{YYYYMMDD}/model.joblib`, `metrics.json`, `feature_list.json`, `config_snapshot.yaml`.
- `score.py` writes to Postgres: `ml.price_forecast` (date, market_key, commodity_key, horizon_date, p10, p50, p90, model_version), `ml.crash_risk` (date, market_key, commodity_key, prob, alert_flag, model_version), and `ml.market_cluster`.
- Set fixed random seeds. Training must be reproducible from a single command:
  `python -m mandipulse ml train-all` and `python -m mandipulse ml score`.
- (Stretch) MLflow local tracking.

---

## 10. Serving layer

### 10.1 Streamlit app (`app/`)

Pages:
1. **Best Mandi This Week** — inputs: commodity, home district (or market), max distance (km), transport cost scenario or custom ₹/qtl/km slider. Output: ranked table of top mandis by **net price** with gain vs home, distance, last-report date; a map with home and candidates. Clear note: "Prices are wholesale modal prices in ₹/quintal; transport costs are estimates."
2. **Price Outlook** — line chart of recent actuals plus the 7-day forecast with p10–p90 band, for a chosen market × commodity.
3. **Crash Alerts** — table of market × commodity pairs currently above the alert threshold, sorted by probability.
4. **Methodology** — data sources, assumptions, limitations, model metrics.

The app reads only from `marts` and `ml` schemas (never from raw). Cache queries with `st.cache_data`.

### 10.2 Power BI dashboard (built by the user)

Claude Code's job: export the tables below to `exports/` (Parquet + CSV) via `python -m mandipulse export`, and make sure the Postgres views are clean for direct connection.

Tables to connect: `dim_date`, `dim_commodity`, `dim_market`, `fact_daily_price`, `mart_price_spread`, `mart_net_price_opportunities`, `mart_seasonality`, `mart_volatility`, `mart_district_access`, `ml.price_forecast`, `ml.crash_risk`, `ml.market_cluster`.

**Pages:**
1. **Overview** — KPI cards: markets tracked, days of data, median same-day gap within 100 km, % of days with a profitable opportunity (mid scenario), avg ₹/qtl gain when an opportunity exists.
2. **Price Spread Explorer** — map of mandis (bubble = median price), slicers for commodity, state, date; table of the biggest gaps.
3. **Seasonality & Volatility** — month × commodity heatmap of price index; perishable vs storable volatility comparison.
4. **Price-Trapped Districts** — district map coloured by `avg_price_index`; table of trapped districts; cluster breakdown.
5. **Forecast & Alerts** — actual vs forecast lines with band; current crash alerts.

**Starter DAX measures:**
```DAX
Median Modal Price = MEDIAN(fact_daily_price[modal_price])

Opportunity Rate (Mid) =
DIVIDE(
    CALCULATE(COUNTROWS(mart_net_price_opportunities),
              mart_net_price_opportunities[scenario] = "mid",
              mart_net_price_opportunities[is_opportunity] = TRUE()),
    CALCULATE(COUNTROWS(mart_net_price_opportunities),
              mart_net_price_opportunities[scenario] = "mid")
)

Avg Gain When Opportunity (Mid) =
CALCULATE(AVERAGE(mart_net_price_opportunities[gain]),
          mart_net_price_opportunities[scenario] = "mid",
          mart_net_price_opportunities[is_opportunity] = TRUE())

Price YoY % =
VAR curr = [Median Modal Price]
VAR prev = CALCULATE([Median Modal Price], SAMEPERIODLASTYEAR(dim_date[date]))
RETURN DIVIDE(curr - prev, prev)
```

Claude Code should also write `powerbi/DASHBOARD_SPEC.md`, expanding this section with exact visuals per page, so the user can follow it step by step.

---

## 11. Repository structure

```
mandi-pulse/
├── README.md                     # Problem → Data → Method → Findings → Limitations
├── MANDI_PULSE_SPEC.md           # this file
├── PROGRESS.md                   # updated by Claude Code after each phase
├── pyproject.toml                # deps + ruff config
├── docker-compose.yml            # postgres
├── .env.example                  # DATA_GOV_API_KEY=, DATABASE_URL=
├── .gitignore                    # data/raw, .env, models/, exports/
├── config/
│   └── settings.yaml             # commodities, states, thresholds, cost scenarios
├── src/mandipulse/
│   ├── __main__.py               # typer CLI
│   ├── config.py
│   ├── db.py                     # SQLAlchemy engine
│   ├── ingest/
│   │   ├── datagov_client.py
│   │   ├── backfill.py
│   │   ├── schemas.py            # pydantic models
│   │   └── load.py               # parquet → postgres raw
│   ├── geo/
│   │   ├── geocode.py
│   │   └── distance.py           # haversine
│   ├── ml/
│   │   ├── features.py
│   │   ├── train_forecast.py
│   │   ├── train_crash.py
│   │   ├── cluster.py
│   │   ├── evaluate.py
│   │   └── score.py
│   └── export.py
├── dbt/mandipulse/
│   ├── dbt_project.yml
│   ├── profiles.example.yml
│   ├── seeds/                    # market_aliases.csv, commodity_aliases.csv, commodity_category.csv
│   ├── models/
│   │   ├── staging/
│   │   ├── intermediate/
│   │   └── marts/
│   ├── macros/
│   └── tests/
├── analysis/queries/             # one .sql per reported number
├── notebooks/
├── app/
│   ├── Home.py
│   └── pages/
├── powerbi/DASHBOARD_SPEC.md
├── reports/
│   ├── figures/
│   ├── tables/
│   └── INSIGHTS_BRIEF.md
├── docs/
│   ├── DATA_SOURCES.md
│   ├── ASSUMPTIONS.md
│   └── DATA_DICTIONARY.md
├── data/
│   ├── raw/                      # gitignored
│   └── reference/                # market_geo.csv, overrides (committed)
├── models/                       # gitignored
├── exports/                      # gitignored
├── tests/
│   ├── fixtures/                 # small synthetic samples ONLY for tests
│   ├── test_client.py
│   ├── test_cleaning.py
│   ├── test_distance.py
│   ├── test_net_price.py
│   └── test_features_no_leakage.py
└── .github/workflows/ci.yml      # ruff + pytest + dbt build on fixture data
```

---

## 12. Build phases & acceptance criteria

### Phase 0 — Setup & data-access spike (≈ 1–2 days)
- Create repo skeleton, `pyproject.toml`, `docker-compose.yml`, `.env.example`, `config/settings.yaml`, CI workflow stub.
- Verify the data.gov.in resource ID, field names, pagination, and rate limits with a tiny script; save a sample response to `tests/fixtures/` (with fields only, no API key).
- Investigate historical sources (6.2) and pick one.
- **Accept when:** `docker compose up` runs Postgres; one real API call succeeds; `docs/DATA_SOURCES.md` documents the chosen daily + historical sources with any caveats.

### Phase 1 — Ingestion & raw load (≈ 3–4 days)
- Implement the API client, backfill, daily job, Parquet writes, `load` into `raw.*`, `ingest_log`.
- Implement geocoding with cache and overrides.
- **Accept when:** backfill has loaded ≥ 1 year (target ≥ 2) for the scoped commodities and states; re-running a date doesn't duplicate rows; ≥ 90% of markets have coordinates (any precision); tests pass.

### Phase 2 — dbt staging, flags, star schema (≈ 3–4 days)
- Seeds, staging models, `int_price_flags`, `int_daily_prices`, dims and fact, all dbt tests.
- **Accept when:** `dbt build` passes; `docs/DATA_DICTIONARY.md` lists every mart column; flag rates are printed in `PROGRESS.md`.

### Phase 3 — Analysis marts & EDA (≈ 3–4 days)
- `int_market_pairs`, all analysis marts, notebooks 01–04, saved queries, figures.
- **Accept when:** Q1–Q5 each have at least one saved query and one figure; numbers are reproducible by re-running the queries.

### Phase 4 — ML (≈ 5–7 days)
- Features with a leakage test, baselines, Model A, Model B, Model C, SHAP, scoring into `ml.*`.
- **Accept when:** walk-forward metrics are saved in `metrics.json` for models and baselines; `reports/ML_REPORT.md` summarises results honestly (including if a model didn't beat baselines); `ml.*` tables are populated.

### Phase 5 — Serving: Streamlit + Power BI prep (≈ 3–4 days)
- Streamlit app (4 pages); `export` command; `powerbi/DASHBOARD_SPEC.md`.
- **Accept when:** `streamlit run app/Home.py` works end to end on real data; exports exist; the dashboard spec is followable step by step.

### Phase 6 — Automation, docs, polish (≈ 2–3 days)
- `python -m mandipulse pipeline` runs the whole daily flow; document how to schedule it (cron / Windows Task Scheduler).
- Final README, `INSIGHTS_BRIEF.md`, `ASSUMPTIONS.md`, screenshots.
- **Accept when:** a fresh clone + README steps reproduces the project; CI is green.

### Phase 7 — Stretch (optional)
- Free cloud Postgres (e.g., Neon/Supabase) + GitHub Actions scheduled daily pipeline; deploy Streamlit to Streamlit Community Cloud.
- Add rainfall features; more commodities and states; MLflow.

---

## 13. Testing strategy

| Test | What it checks |
|---|---|
| `test_client.py` | Pagination, retries, and reject handling using mocked responses (`responses` or `requests-mock`) |
| `test_cleaning.py` | Name normalisation, date parsing, dedupe logic |
| `test_distance.py` | Haversine on known city pairs (within 1% tolerance) |
| `test_net_price.py` | Transport cost and gain formula, scenario handling, edge cases |
| `test_features_no_leakage.py` | No feature at time *t* uses data from > *t* (shift a future value and assert features don't change) |
| dbt tests | Keys, relationships, accepted values, modal between min/max, freshness |

CI runs ruff, pytest, and `dbt build` against a Postgres service container seeded with fixture data.

---

## 14. Assumptions & limitations (must appear in README and app)

- Modal price is a wholesale indicator, not the exact price any individual farmer receives.
- Transport cost uses straight-line distance × 1.3 and flat ₹/qtl/km rates. Real costs vary by vehicle, load, and road. Results are therefore shown as low/mid/high ranges.
- Geocoding may fall back to district centroids for some mandis (tracked by `geo_precision`).
- Reporting gaps: markets don't report daily; small mandis report irregularly.
- Selling elsewhere also involves non-price factors (commission agent relationships, payment delays, perishability during transit) not modelled here.
- ML models are evaluated on historical data; performance can shift with policy changes (e.g., export bans) and unusual weather.

---

## 15. README & insights brief templates

### README outline
1. **One-line pitch + hero screenshot** (dashboard or app)
2. **The problem** (3–4 sentences, with one striking real number from your data)
3. **What I built** (architecture diagram)
4. **Key findings** (3–5 bullets, each with a number and a link to the query that produced it)
5. **ML results** (table: model vs baselines; one SHAP plot; plain-English drivers)
6. **Data quality** (flag rates, how they were handled)
7. **How to run it** (setup, `.env`, commands)
8. **Assumptions & limitations**
9. **What I'd do next**

### `reports/INSIGHTS_BRIEF.md` (one page, consultant style)
- **Headline:** one sentence, with the most important finding.
- **Context:** why this matters (2–3 sentences).
- **Findings:** 3 numbered findings, each with a number and a "so what".
- **Recommendations:** 2–3 actions for (a) farmers/FPOs, (b) policymakers or APMC boards.
- **Caveats:** 2–3 bullets.

---

## 16. Resume bullet templates (fill only with real results)

- Built an automated data pipeline (Python, PostgreSQL, dbt) ingesting **[N] lakh** daily mandi price records across **[M] markets** in **[S] states**, with **[K] data-quality tests** catching **[X]%** invalid records.
- Quantified intra-regional price gaps: in **[Y]%** of market-days, a mandi within 100 km offered **₹[G]/quintal** more *after* transport costs; identified **[D] price-trapped districts**.
- Developed a LightGBM 7-day price forecast that cut MAE by **[P]%** vs. baselines, and a crash early-warning model (PR-AUC **[A]**, avg lead time **[L] days**), explained with SHAP.
- Delivered insights through a 5-page Power BI dashboard and a Streamlit "best mandi" decision tool.

---

## 17. Config reference (`config/settings.yaml` starter)

```yaml
scope:
  commodities: ["Tomato", "Onion", "Potato"]
  exclude_commodities: ["Onion Green", "Sweet Potato"]
  states: ["Maharashtra", "Madhya Pradesh", "Uttar Pradesh", "Gujarat"]
  backfill_start: "2018-01-01"

periods:
  main:               { start: "2018-01-01", end: "2025-10-31" }
  post_format_change: { start: "2025-11-01" }

sources:   # precedence: kaggle (history) -> ceda (cross-check + arrivals) -> datagov (daily, later)
  kaggle:  { parquet_glob: "data/raw/kaggle/*.parquet", source_tag: "kaggle_archive" }
  ceda:    { enabled: false, source_tag: "ceda" }
  datagov: { enabled: false, source_tag: "datagov_daily" }

api:
  datagov_resource_id: "9ef84268-d588-465a-a308-a864a43d0070"   # verify in Phase 0
  page_size: 1000
  timeout_s: 30
  max_retries: 5

geo:
  nominatim_user_agent: "mandi-pulse-portfolio (contact: <your-email>)"
  min_delay_s: 1.0
  road_factor: 1.3
  max_pair_km: 150
  spread_radius_km: 100

quality:
  outlier_log_ratio: 1.0986        # ln(3)
  unit_bounds_per_qtl: { min: 50, max: 20000 }

opportunity:
  min_gain_abs: 100
  min_gain_pct: 0.05
  scenarios:
    low:  { cost_per_qtl_km: 1.0, fixed_cost_per_qtl: 30 }
    mid:  { cost_per_qtl_km: 1.5, fixed_cost_per_qtl: 50 }
    high: { cost_per_qtl_km: 2.5, fixed_cost_per_qtl: 80 }

district_access:
  near_radius_km: 50
  trapped_max_markets: 2
  trapped_max_price_index: 0.9

ml:
  random_seed: 42
  min_series_days: 180
  ffill_limit_days: 3
  forecast_horizon_days: 7
  quantiles: [0.1, 0.5, 0.9]
  walk_forward_test_months: ["2025-05", "2025-06", "2025-07", "2025-08", "2025-09", "2025-10"]
  crash:
    horizon_days: 14
    lookback_days: 30
    drop_ratio: 0.7
    target_precision: 0.6
  cluster_k_range: [3, 4, 5, 6]
```

---

## 18. First prompt to give Claude Code

> Read `MANDI_PULSE_SPEC.md` fully. Then do **Phase 0 only**: set up the repo skeleton, Docker Postgres, config, and CI stub, and run the data-access spike. Verify the data.gov.in API with my key from `.env`, investigate historical data sources, and document your findings in `docs/DATA_SOURCES.md` and `PROGRESS.md`. Stop after Phase 0 and summarise what you found, including anything in the spec that needs to change.
