-- Q4. Every district x commodity with its access metrics (price-trapped first).
select state, district, commodity, n_markets_within_50km, avg_price_index,
       round(100 * opportunity_rate, 1) as opportunity_rate_pct, is_price_trapped,
       n_markets_within_50km_market_precision, is_price_trapped_market_precision, n_price_days
from marts.mart_district_access
order by is_price_trapped desc, avg_price_index, state, district, commodity;
