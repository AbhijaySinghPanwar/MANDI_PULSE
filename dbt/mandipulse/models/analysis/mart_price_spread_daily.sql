-- Q1 rollup: per commodity x state x date, the distribution of same-day pair gaps.
-- A cross-state pair counts in both of its states.

with sides as (
    select date, commodity, state_a as state, abs_gap, pct_gap, pair_precision
    from {{ ref('mart_price_spread') }}
    union all
    select date, commodity, state_b, abs_gap, pct_gap, pair_precision
    from {{ ref('mart_price_spread') }}
    where not is_same_state
)

select
    date,
    commodity,
    state,
    count(*)                                                                      as n_pairs,
    percentile_cont(0.5) within group (order by abs_gap)::numeric(12, 2)         as median_abs_gap,
    percentile_cont(0.9) within group (order by abs_gap)::numeric(12, 2)         as p90_abs_gap,
    percentile_cont(0.5) within group (order by pct_gap)::numeric(8, 4)          as median_pct_gap,
    percentile_cont(0.9) within group (order by pct_gap)::numeric(8, 4)          as p90_pct_gap
from sides
group by date, commodity, state
