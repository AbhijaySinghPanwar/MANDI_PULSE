-- Rows per yearly file, and rows whose arrival_date falls outside the file's year.
select
    file_year,
    count(*)                                                as n_rows,
    min(arrival_date)                                       as first_date,
    max(arrival_date)                                       as last_date,
    count(*) filter (where year(arrival_date) <> file_year) as n_rows_other_year
from prices
group by file_year
order by file_year;
