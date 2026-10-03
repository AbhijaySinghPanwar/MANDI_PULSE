-- EDA. Coverage per state x crop in the analysis base (main period, valid, suspect-low excluded).
with per_market_year as (
    select state, commodity, market_key, extract(year from date)::int as year, count(*) as report_days
    from marts.int_analysis_prices
    group by 1, 2, 3, 4
)
select state, commodity,
       count(distinct market_key)                                                as n_markets,
       sum(report_days)                                                          as n_market_days,
       round(percentile_cont(0.5) within group (order by report_days)::numeric)  as median_report_days_per_market_year
from per_market_year
group by 1, 2
order by 1, 2;
