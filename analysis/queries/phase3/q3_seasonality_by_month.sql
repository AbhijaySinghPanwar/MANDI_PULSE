-- Q3. Per commodity x calendar month (all four states pooled):
--   median_price_index  median across states of the month price index (month median / annual median)
--   crash_rate_pct      share of labelled market-days that are crashes (spec 9.2: within the next
--                       14 days the price falls below 70% of its trailing 30-day median), observed days only
select
    commodity,
    month,
    min(month_name)                                                               as month_name,
    round(percentile_cont(0.5) within group (order by price_index)::numeric, 3)   as median_price_index,
    sum(n_labelled_days)                                                          as n_labelled_days,
    sum(n_crash_days)                                                             as n_crash_days,
    round(100.0 * sum(n_crash_days) / nullif(sum(n_labelled_days), 0), 2)         as crash_rate_pct
from marts.mart_seasonality
group by 1, 2
order by 1, 2;
