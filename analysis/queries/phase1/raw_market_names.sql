-- Every distinct raw market name in raw.mandi_prices, with its activity span.
select state, district, market, count(*) as n_rows,
       min(arrival_date) as first_date, max(arrival_date) as last_date
from raw.mandi_prices
group by 1, 2, 3
order by 1, 2, 3;
