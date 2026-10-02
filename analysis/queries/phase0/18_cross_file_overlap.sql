-- 2026.parquet contains rows dated late Dec 2025. How many are also present in 2025.parquet?
with late as (
    select * exclude (file_year) from prices where file_year = 2026 and year(arrival_date) = 2025
),
early as (
    select * exclude (file_year) from prices where file_year = 2025 and arrival_date >= date '2025-12-01'
)
select
    (select count(*) from late)                              as n_rows_2025_dates_in_2026_file,
    (select count(*) from (select * from late intersect all select * from early)) as n_also_in_2025_file,
    (select max(arrival_date) from early)                    as last_date_in_2025_file;
