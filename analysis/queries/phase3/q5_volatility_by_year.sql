-- Q5. Median CV per commodity x year (does the perishable/storable gap hold every year?).
select year, commodity, category, count(*) as n_market_years,
       round(percentile_cont(0.5) within group (order by cv)::numeric, 3) as median_cv
from marts.mart_volatility
group by 1, 2, 3
order by 1, 2;
