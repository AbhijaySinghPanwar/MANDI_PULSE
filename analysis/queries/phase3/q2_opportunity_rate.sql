-- Q2. Share of market-days (home market and >= 1 neighbour within 100 km reported) on which at
-- least one destination pays more AFTER transport cost (gain >= Rs 100 and >= 5%), per scenario.
-- Also: the per-comparison rate (one specific neighbour) and the median best gain.
with md as (
    select scenario, commodity,
           count(*)                                       as n_market_days,
           round(100.0 * avg(has_opportunity::int), 1)    as pct_market_days_with_opportunity,
           round(percentile_cont(0.5) within group (order by best_opportunity_gain)::numeric)
                                                          as median_best_gain_rs_qtl,
           round(avg(n_neighbors_reporting), 1)           as avg_neighbors_reporting
    from marts.mart_opportunity_market_day
    group by 1, 2
),
pc as (
    select scenario, commodity, round(100.0 * avg(is_opportunity::int), 1) as pct_single_comparisons_opportunity
    from marts.int_directed_comparisons
    group by 1, 2
)
select md.*, pc.pct_single_comparisons_opportunity
from md join pc using (scenario, commodity)
order by commodity, case scenario when 'low' then 1 when 'mid' then 2 else 3 end;
