-- Median report days per month for a market x commodity series, Jan 2023 onwards.
-- Shows reporting thinning through 2025 and collapsing after the Nov-2025 change.
with m as (
    select state, district, market, commodity, strftime(arrival_date, '%Y-%m') as month,
           count(distinct arrival_date) as report_days, count(*) as n_rows
    from scope_prices
    where arrival_date >= date '2023-01-01'
    group by all
)
select month, count(*) as n_series_reporting, median(report_days) as median_report_days,
       median(n_rows) as median_rows
from m
group by month
order by month;
