# Assumptions

Every assumption the numbers depend on, grouped by pipeline stage. Thresholds live in [`config/settings.yaml`](../config/settings.yaml), which is the single source of truth; dbt receives them as `--vars`. Last updated: 2026-10-07 (Phase 6).

## Scope and sources

- **Crops:** tomato, onion and potato. Names match the archive exactly; the look-alikes "Onion Green" and "Sweet Potato" are explicitly excluded.
- **States:** Maharashtra, Madhya Pradesh, Uttar Pradesh and Gujarat, which form one contiguous block, so the ≤ 100 km pairs cross state borders.
  - **Tamil Nadu dropped:** about 92% of its recent rows are *Uzhavar Sandhai* farmer-to-consumer markets with near-retail prices (about 2× Maharashtra wholesale). Its other markets often enter prices per kg, and it has no data from 2013 to mid-2024.
  - **Karnataka dropped:** too few market series with ≥ 180 report days a year.
  - Details: [DATA_SOURCES.md §1.7 and §4](DATA_SOURCES.md).
- **Period:** rows from 2018-01-01 are loaded.
  - **Analysis, models and app use 2018-01-01 → 2025-10-31** (`period = main`).
  - Rows from 2025-11-01 (`post_format_change`) are loaded but not analysed. After the Nov-2025 source change, reporting density collapsed (median 2–7 report days per series a month), and that has not yet been checked against CEDA.
- **Source:** the Kaggle archive of Agmarknet data (GODL-India) is the only price source used. CEDA (cross-check and arrivals) and the data.gov.in daily API are planned but not called.
- **Units:** prices are wholesale **modal prices in ₹ per quintal (100 kg)**. A modal price is a market-day indicator, not the price an individual farmer receives; it mixes varieties and grades.

## Market identity and locations (Phase 1)

- **APMC suffix:** from Nov 2025 the source renamed markets "X" → "X APMC". The suffix is stripped, so both are one market.
- **Merge rule:** two market names are merged only if they are in the same district (after district corrections) **and** never report on the same date, checked against everything already merged into the target.
  - 43 doubtful cases were reviewed by hand: 38 merged, 5 kept separate. Every decision and its reason is in [`reports/tables/phase1/market_alias_review.csv`](../reports/tables/phase1/market_alias_review.csv).
  - Canonical markets went from 633 to 595.
- **District names** are kept as in the data (older names); a few misfiled districts are corrected via `data/reference/`.
- **Geocoding:** each market is geocoded with OpenStreetMap Nominatim (1 request/s, cached in `data/reference/market_geo.csv`).
  - A hit more than 100 km from its district centre is rejected.
  - Markets that are not found, or are rejected, get the **district centre** (`geo_precision = district_centroid`): 23.9% of markets. Their distances are approximate. Robustness version (b) drops them.
- **Road distance** = straight-line (haversine) distance × **1.3**.
- **Pair limits:** pairs are formed up to 150 km; the spread analysis uses pairs ≤ 100 km.

## Data quality (Phase 2)

- **Flagging:** rows are flagged, never deleted. A daily price uses only rows with no flag.
- **Invalid rows:**
  - a modal price ≤ 0;
  - modal below the min or above the max (or min > max);
  - a price outside ₹50–20,000/qtl (unit errors);
  - outliers (below).
  - Result: 2,697 of 1,826,981 in-scope rows (0.15%).
- **Outliers are judged against the market's own previous 30 days AND the same-day median of the state's markets.**
  - A price is an outlier only if it is more than 3× away from **both**.
  - If fewer than 3 markets in the state report that day, only the market's own history is used. If the market has fewer than 5 prior report days, it is not checked.
  - *Why (the July 2023 tomato example):* in July 2023 tomato prices rose about 5–8× across India within weeks. The median modal across our markets was ₹1,265/qtl in June, ₹7,000/qtl in July and ₹4,067/qtl in August.
    - The spec's original rule (own history only) flagged **24.0% of all tomato rows in July 2023** (1,449 rows), and 9.4% in June.
    - The tuned rule flags **0.3%** (21 rows), because every market moved together.
    - Keeping the original rule would have deleted exactly the spikes and crashes the models must learn. Source: [`07_outlier_rule_comparison.sql`](../analysis/queries/phase2/07_outlier_rule_comparison.sql).
  - The original rule's result is kept per row as `flag_outlier_temporal`, for transparency.
- **A min or max price of 0 is treated as missing**, not as an error. These are placeholders in older records; the modal price on the same row is used if it passes the other checks.
- **Suspect-low series (`flag_persistent_low`):** markets whose valid prices sit more than 3× below the same-day state median on at least 30 days, making up at least 10% of the series.
  - This covers 22 market × crop series and 3,718 rows.
  - They are *not* invalid, but the headline analysis, the models' evaluation, Best Mandi and Crash Risk exclude them. A sensitivity version includes them.
  - They will be cross-checked against CEDA. List: [`suspect_low_markets.csv`](../reports/tables/phase2/suspect_low_markets.csv).
- **Markets with no valid price** (`dim_market.has_valid_data = false`) are excluded everywhere.
- **Daily price** = median of the valid modal prices across varieties and grades. Days without a valid report have no row; there is no gap filling in the marts.
- **Duplicates** (same date, market, crop, variety, grade) keep the latest ingested copy.

## Net-price opportunities (Phases 3 / 3.1)

- **Transport cost** = road distance × ₹ per quintal per km + a fixed handling cost per quintal:

  | Scenario | Freight (₹/qtl/km) | Handling (₹/qtl) |
  |---|---|---|
  | Low | 1.0 | 30 |
  | Mid | 1.5 | 50 |
  | High | 2.5 | 80 |

- **Commission and market fees** = 4% / 6% / 8% of the **destination** price (low / mid / high).
  - These fees **vary by state and by market**: the APMC market fee, the commission agent's *aadhat*, and loading and weighing charges. A single percentage is a simplification; the three scenarios bracket the typical range.
  - Fees are charged only at the destination. This is conservative: selling at home also incurs fees, so the true advantage of moving is somewhat larger than computed.
  - Spoilage in transit (relevant for tomato), payment delays and relationships with commission agents are not modelled.
- **An opportunity** needs a gain of at least ₹100 per quintal **and** at least 5% of the home price, after both costs.
- **Same-day only:** both prices must be from the same date. Headline rates are per home market-day: "at least one neighbour ≤ 100 km paid more".
- **Same-variety check:** a robustness version compares only the same named variety at both markets on the same day; the catch-all variety "Other" is excluded. It lowers the mid rate from 33.8% to 24.4%.

## District access (Q4)

- **Price-trapped district × crop:** at most 2 market *towns* with data within 50 km (several yards in one town count once), **and** an average price below 90% of the state's same-day median.

## Crash label (Phase 3.1)

- A **crash** at a market on day t means that on **at least 2 report days** within the next 14 days, the price is below 70% of the median of its last 30 days. Only real reports count.
- The label is unknown (NULL) when the lookback has fewer than 5 report days, or when there is no report in the horizon.
- The original rule (a single low report within 14 days) was dropped, because one mis-keyed or low-quality quote was enough to trigger it.

## Models (Phase 4 / 4.1)

- **No leakage:** features at anchor day t use only data up to t.
  - A price may be forward-filled for at most 3 days, and only as a feature.
  - **Targets are real reports**; a filled value is never a target.
  - Training data never contains a target dated inside the test month.
  - Enforced by `tests/test_features_no_leakage.py`.
- **Model A (7-day forecast):** one global LightGBM on the 7-day log-price change, with quantile objectives p10 / p50 / p90. It covers series with ≥ 180 report days.
  - **Test:** walk-forward on May–Oct 2025, one month at a time. The model is retrained on all targets before each month.
  - **Objective:** median (L1). It was chosen after a first L2 run and then **confirmed on a pre-test window** (Nov 2024 – Apr 2025, targets before 2025-05-01), where L1 also won.
  - **Band:** the p10–p90 range is widened per crop by a conformal (CQR) factor fitted on that validation window only, and kept in order (p10 ≤ p50 ≤ p90).
- **Model B (crash warning):** LightGBM with the same features, plus slopes, the share of the state's markets falling, and the crop × month historical crash rate (training data only).
  - **Validation:** yearly expanding folds (2022, 2023, 2024, Jan–Oct 2025), because the May–Oct test window contains no December.
  - **Alert threshold:** chosen on the previous year for a precision of 0.6. This target is not reached on not-yet-falling days (30%).
  - **Honest headline:** measured on days when the price is still ≥ 90% of its 30-day median, because 73.8% of crash labels fall on days already below that.
- **Model C (segments):** k-means on standardised per-series features. k = 5 was chosen among 3–6 by silhouette (within 0.02 of the best) and interpretability.
- **Random seed:** 42.

## App and exports (Phases 5 / 5.1)

- **"Data as of"** is the latest date in the analysis data (31 Oct 2025), read from the data, not hard-coded.
- **Latest price** = the most recent report in the last 30 days of the data. **"Falling now"** = the latest report is below 90% of its 30-day median: a rule, no model.
- **Early-warning levels:** High = score ≥ the validated alert threshold; Medium = ≥ half of it; Low otherwise. Shown only for series that are not already falling.
- **"Verify before acting"** badge: the latest report is either
  - (a) more than 3× below or above the same-day median of the state's markets, or
  - (b) below 60% of the median of markets within 50 km (straight line, other towns) on the same day, or within ±1 day if none reported that day, or
  - (c) a single low report (< 90% of the 30-day median) whose previous report was not low.
  - Thresholds are in `config/settings.yaml` → `app.verify`.
  - Badged entries are listed after the confirmed ones and are not counted as gains in Best Mandi.
- **Best Mandi** uses each market's latest price, so the two dates may differ by a few days; the table shows both report dates. Destinations in the same town as the home market are not shown.
- **Power BI exports:** the three pair-level marts are exported as monthly aggregates plus the latest 90 days of detail. The full tables stay in Postgres.
- **Deployed app:** reads a committed 2.7 MB snapshot (`data/app_snapshot/`) produced by the same SQL as the Postgres backend.
