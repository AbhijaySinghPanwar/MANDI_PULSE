-- Sanity: mid-scenario opportunity rate by state of the home market (UP dominates market-days).
select m.state, o.commodity,
       count(*)                                         as n_market_days,
       round(100.0 * count(*) / sum(count(*)) over (partition by o.commodity), 1) as pct_of_commodity_market_days,
       round(100.0 * avg(o.has_opportunity::int), 1)    as pct_with_opportunity,
       round(avg(o.n_neighbors_reporting), 1)           as avg_neighbors
from marts.mart_opportunity_market_day o
join marts.dim_market m on m.market_key = o.home_market_key
where o.scenario = 'mid'
group by 1, 2
order by 2, 1;
