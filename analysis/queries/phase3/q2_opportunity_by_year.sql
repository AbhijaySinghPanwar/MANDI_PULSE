-- Q2. Mid-scenario opportunity rate by year and commodity.
select
    extract(year from date)::int                    as year,
    commodity,
    count(*)                                        as n_market_days,
    round(100.0 * avg(has_opportunity::int), 1)     as pct_market_days_with_opportunity
from marts.mart_opportunity_market_day
where scenario = 'mid'
group by 1, 2
order by 1, 2;
