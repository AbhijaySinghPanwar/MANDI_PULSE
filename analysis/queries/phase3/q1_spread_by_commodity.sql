-- Q1. Same-day price gap between market pairs <= 100 km (road estimate), main period 2018-01-01..2025-10-31.
-- Pair-days where both markets reported. pct_gap = |gap| / the lower price.
select
    commodity,
    count(*)                                                                      as n_pair_days,
    count(distinct pair_key)                                                      as n_pairs,
    round(percentile_cont(0.5) within group (order by abs_gap)::numeric)          as median_abs_gap_rs_qtl,
    round(percentile_cont(0.9) within group (order by abs_gap)::numeric)          as p90_abs_gap_rs_qtl,
    round(100 * percentile_cont(0.5) within group (order by pct_gap)::numeric, 1) as median_pct_gap,
    round(100 * percentile_cont(0.9) within group (order by pct_gap)::numeric, 1) as p90_pct_gap,
    round(100.0 * avg((pct_gap >= 0.20)::int), 1)                                 as pct_pair_days_gap_ge_20pct
from marts.mart_price_spread
group by commodity
order by commodity;
