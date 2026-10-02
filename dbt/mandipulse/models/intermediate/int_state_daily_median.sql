-- Same-day cross-section per state x commodity: median of the markets' daily baseline prices.
-- Used by the outlier flag to tell a genuine market-wide move (all markets jump together, e.g.
-- the July 2023 tomato spike) from a single-market entry error.

select
    state,
    commodity,
    arrival_date,
    percentile_cont(0.5) within group (order by baseline_modal) as state_median,
    count(*)                                                     as n_markets
from {{ ref('int_daily_baseline') }}
group by state, commodity, arrival_date
