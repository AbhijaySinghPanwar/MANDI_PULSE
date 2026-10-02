-- Monthly rows per commodity x state for the whole history (feeds charts and gap review).
select commodity, state, strftime(arrival_date, '%Y-%m') as month, count(*) as n_rows,
       count(distinct arrival_date) as days_with_data,
       count(distinct district || '|' || market) as n_markets
from scope_prices
group by all
order by commodity, state, month;
