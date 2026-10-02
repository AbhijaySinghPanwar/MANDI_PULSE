-- Postgres: rows loaded into raw.mandi_prices per commodity x state x year (Kaggle source).
select commodity, state, extract(year from arrival_date)::int as year, count(*) as n_rows_raw
from raw.mandi_prices
where source = 'kaggle_archive'
group by 1, 2, 3
order by 1, 2, 3;
