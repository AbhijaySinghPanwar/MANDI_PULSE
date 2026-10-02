-- Variety and grade labels in scope (needed for the aggregation rule in spec 7.4).
select commodity, variety, grade, count(*) as n_rows
from scope_prices
group by all
order by commodity, n_rows desc;
