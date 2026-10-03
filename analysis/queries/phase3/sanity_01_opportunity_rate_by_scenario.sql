-- Sanity: Q2 opportunity rate (spec definition) by scenario x commodity, with the average number
-- of neighbours reporting. Rate = share of home market-days (with >= 1 neighbour within 100 km
-- reporting) on which at least one destination is profitable after transport cost.
select
    scenario, commodity,
    count(*)                                                                   as n_market_days,
    round(100.0 * avg(has_opportunity::int), 1)                                as pct_market_days_with_opportunity,
    round(avg(n_neighbors_reporting), 1)                                       as avg_neighbors_reporting,
    round(percentile_cont(0.5) within group (order by best_opportunity_gain)::numeric) as median_best_gain_when_opportunity
from marts.mart_opportunity_market_day
group by 1, 2
union all
select scenario, 'All', count(*), round(100.0 * avg(has_opportunity::int), 1),
       round(avg(n_neighbors_reporting), 1),
       round(percentile_cont(0.5) within group (order by best_opportunity_gain)::numeric)
from marts.mart_opportunity_market_day
group by 1
order by 1, 2;
