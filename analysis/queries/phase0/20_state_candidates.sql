-- Scope check across ALL states (not just the configured ones): for Tomato/Onion/Potato,
-- how many market series report on >= 180 days in a year, per year 2018-2025.
-- A series = state x district x market x commodity. Used to recommend which states to keep.
with series_year as (
    select state, district, market, commodity, year(arrival_date) as year,
           count(distinct arrival_date) as report_days
    from prices
    where commodity in ('Tomato', 'Onion', 'Potato')
      and arrival_date between date '2018-01-01' and date '2025-12-31'
    group by all
)
select
    state, commodity,
    count(*) filter (where year = 2018 and report_days >= 180) as y2018,
    count(*) filter (where year = 2019 and report_days >= 180) as y2019,
    count(*) filter (where year = 2020 and report_days >= 180) as y2020,
    count(*) filter (where year = 2021 and report_days >= 180) as y2021,
    count(*) filter (where year = 2022 and report_days >= 180) as y2022,
    count(*) filter (where year = 2023 and report_days >= 180) as y2023,
    count(*) filter (where year = 2024 and report_days >= 180) as y2024,
    count(*) filter (where year = 2025 and report_days >= 180) as y2025
from series_year
group by all
having sum(case when report_days >= 180 then 1 else 0 end) > 0
order by commodity, (y2022 + y2023 + y2024) desc;
