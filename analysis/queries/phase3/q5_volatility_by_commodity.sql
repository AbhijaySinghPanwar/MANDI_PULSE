-- Q5. Volatility per commodity (perishable tomato vs storable onion/potato): medians over
-- market-years with >= 60 report days.
select
    commodity,
    category,
    count(*)                                                                              as n_market_years,
    round(percentile_cont(0.5) within group (order by cv)::numeric, 3)                    as median_cv,
    round(100 * percentile_cont(0.5) within group (order by avg_abs_daily_pct_change)::numeric, 1)
                                                                                          as median_avg_abs_daily_change_pct,
    round(100 * percentile_cont(0.5) within group (order by max_drawdown)::numeric, 1)    as median_max_drawdown_pct
from marts.mart_volatility
group by 1, 2
order by 1;
