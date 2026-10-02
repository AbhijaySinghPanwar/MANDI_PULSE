# Assumptions

Filled in from Phase 3 onward. Starting points are in MANDI_PULSE_SPEC.md Section 14.

## Data (from Phase 0 profiling)

- Prices are wholesale modal prices in ₹/quintal. Tamil Nadu Uzhavar Sandhai markets are farmer-to-consumer (near-retail) and are not comparable; see docs/DATA_SOURCES.md 1.7.
- Market identity across the Nov-2025 renaming (`X` → `X APMC`) is resolved by stripping "APMC" into `market_clean`.

## Data quality (Phase 2)

- Rows are flagged, never deleted. A daily price uses only rows with no flag.
- Outliers are judged against the market's own previous 30 days **and** the same-day state median: a move shared by the whole state is treated as real, not an error (see PROGRESS.md, Phase 2).
- Daily price = median of the valid modal prices across varieties and grades. Days without a valid report have no row (no gap filling).
- Duplicate rows (same date, market, commodity, variety, grade) keep the latest ingested copy.
- Market identity: names are merged only within a district, and only if they never report on the same date.
