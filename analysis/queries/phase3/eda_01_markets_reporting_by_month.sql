-- EDA. Markets reporting at least one valid price (any crop) per month and state, main period.
select date_trunc('month', date)::date as month, state,
       count(distinct market_key)       as n_markets_reporting,
       count(*)                         as n_market_crop_days
from marts.int_analysis_prices
group by 1, 2
order by 1, 2;
