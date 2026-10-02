-- Slow (reads 6.5 GB). Confirms the CSV copy has the same row count and date range as Parquet.
select 'csv' as format, count(*) as n_rows,
       min("Arrival_Date") as first_date, max("Arrival_Date") as last_date
from csv_prices
union all
select 'parquet', count(*), min(arrival_date_raw), max(arrival_date_raw)
from prices;
