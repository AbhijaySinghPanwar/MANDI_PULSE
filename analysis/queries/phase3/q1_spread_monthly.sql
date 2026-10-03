-- Q1. Monthly median of the same-day pct gap per commodity (all states), for the time-series chart.
select
    date_trunc('month', date)::date                                               as month,
    commodity,
    count(*)                                                                      as n_pair_days,
    round(100 * percentile_cont(0.5) within group (order by pct_gap)::numeric, 1) as median_pct_gap,
    round(100 * percentile_cont(0.9) within group (order by pct_gap)::numeric, 1) as p90_pct_gap
from marts.mart_price_spread
group by 1, 2
order by 1, 2;
