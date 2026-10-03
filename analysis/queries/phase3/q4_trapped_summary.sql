-- Q4. How many districts are price-trapped (<= 2 town locations with data within 50 km AND
-- average price < 90% of the state price on the same days), per commodity.
select
    commodity,
    count(*)                                                        as n_districts,
    count(*) filter (where is_price_trapped)                        as n_trapped,
    count(*) filter (where n_markets_within_50km <= 2)              as n_thin_access,
    count(*) filter (where avg_price_index < 0.9)                   as n_low_price,
    round(100.0 * avg(opportunity_rate) filter (where is_price_trapped), 1)     as opp_rate_pct_trapped,
    round(100.0 * avg(opportunity_rate) filter (where not is_price_trapped), 1) as opp_rate_pct_others
from marts.mart_district_access
group by 1
order by 1;
