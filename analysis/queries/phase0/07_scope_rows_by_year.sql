-- In-scope row counts per commodity x state x year.
select commodity, state, year(arrival_date) as year, count(*) as n_rows
from scope_prices
group by all
order by commodity, state, year;
