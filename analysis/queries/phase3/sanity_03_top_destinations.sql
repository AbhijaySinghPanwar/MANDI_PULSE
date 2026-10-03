-- Sanity: the 15 destination markets with the most mid-scenario opportunities.
select m.state, m.district, m.market, m.geo_precision,
       count(*)                       as n_opportunities,
       round(avg(o.gain))             as avg_gain,
       round(avg(o.road_km_est))      as avg_road_km
from marts.mart_net_price_opportunities o
join marts.dim_market m on m.market_key = o.dest_market_key
where o.scenario = 'mid'
group by 1, 2, 3, 4
order by n_opportunities desc
limit 15;
