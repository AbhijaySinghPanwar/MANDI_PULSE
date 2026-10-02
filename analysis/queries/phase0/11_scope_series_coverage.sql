-- Market-level coverage in the dense window 2023-11-01..2025-10-31 (the 2 years before
-- the Nov-2025 source change). A series = district x market x commodity.
-- The ML spec (9.1) drops series with < 180 valid days.
with series as (
    select commodity, state, district, market, count(distinct arrival_date) as report_days
    from scope_prices
    where arrival_date between date '2023-11-01' and date '2025-10-31'
    group by all
)
select
    commodity, state,
    count(*)                                   as n_series,
    count(*) filter (where report_days >= 180) as n_series_180d,
    count(*) filter (where report_days >= 365) as n_series_365d,
    median(report_days)                        as median_report_days
from series
group by all
order by commodity, state;
