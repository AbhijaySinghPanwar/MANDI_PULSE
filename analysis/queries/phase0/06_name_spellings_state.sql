-- Every state spelling in the archive.
select state, count(*) as n_rows, min(arrival_date) as first_date, max(arrival_date) as last_date
from prices
group by state
order by state;
