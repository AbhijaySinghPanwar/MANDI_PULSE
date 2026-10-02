-- Exact commodity spellings containing our scope words (includes look-alikes to exclude).
select commodity, commodity_code, count(*) as n_rows,
       min(arrival_date) as first_date, max(arrival_date) as last_date
from prices
where commodity ilike '%tomato%' or commodity ilike '%onion%' or commodity ilike '%potato%'
group by all
order by n_rows desc;
