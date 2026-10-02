# Assumptions

Filled in from Phase 3 onward. Starting points are in MANDI_PULSE_SPEC.md Section 14.

## Data (from Phase 0 profiling)

- Prices are wholesale modal prices in ₹/quintal. Tamil Nadu Uzhavar Sandhai markets are farmer-to-consumer (near-retail) and are not comparable; see docs/DATA_SOURCES.md 1.7.
- Market identity across the Nov-2025 renaming (`X` → `X APMC`) is resolved by stripping "APMC" into `market_clean`.

## Data quality (Phase 2)

- Rows are flagged, never deleted. A daily price uses only rows with no flag.
- **Outliers are judged against the market's own previous 30 days AND the same-day median of the state's markets.** A price is an outlier only if it is more than 3x away from both. If fewer than 3 markets in the state report that day, only the market's own history is used.
  - *Why (the July 2023 tomato example):* in July 2023 tomato prices rose about 5-8x across India within weeks (median modal across our markets: Rs 1265/qtl in June, Rs 7000/qtl in July, Rs 4067/qtl in August). The spec's original rule, which compares only with the market's own previous 30 days, flagged **24.0% of all tomato rows in July 2023** (1449 rows) and 9.4% in June. Under the tuned rule it is **0.3%** (21 rows), because every market moved together. Keeping the original rule would have deleted exactly the spikes and crashes the forecasting and crash models must learn. Source: `analysis/queries/phase2/07_outlier_rule_comparison.sql`.
  - The original rule's result is kept per row as `flag_outlier_temporal`, for transparency.
- **A min or max price of 0 is treated as missing**, not as an error. These are placeholders in older records; the modal price on the same row is used if it passes the other checks.
- **Suspect-low series (`flag_persistent_low`)** are markets whose valid prices sit more than 3x below the same-day state median on many days (at least 30 days and at least 10% of the series). They are *not* invalid, but the headline analysis excludes them; a sensitivity version includes them. They will be cross-checked against CEDA. List: `reports/tables/phase2/suspect_low_markets.csv`.
- Markets with no valid price at all (`dim_market.has_valid_data = false`) are excluded from all analysis.
- Daily price = median of the valid modal prices across varieties and grades. Days without a valid report have no row (no gap filling).
- Duplicate rows (same date, market, commodity, variety, grade) keep the latest ingested copy.
- Market identity: names are merged only within a district, and only if they never report on the same date.
