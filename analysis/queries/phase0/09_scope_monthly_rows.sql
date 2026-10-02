-- Monthly rows and markets per state (all 3 commodities) from 2022, to locate coverage breaks.
select strftime(arrival_date, '%Y-%m') as month, state, count(*) as n_rows,
       count(distinct district || '|' || market) as n_markets
from scope_prices
where arrival_date >= date '2022-01-01'
group by all
order by month, state;
