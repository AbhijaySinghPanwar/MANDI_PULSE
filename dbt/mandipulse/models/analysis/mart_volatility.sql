-- Q5. Per commodity x market x year (years with >= 60 report days):
--   cv                       std / mean of daily prices
--   avg_abs_daily_pct_change mean |% change| between consecutive reports <= 3 days apart
--   max_drawdown             largest fall from a running peak within the year (0.4 = -40%)

with p as (
    select market_key, state, commodity, category, date, modal_price,
           extract(year from date)::int as year
    from {{ ref('int_analysis_prices') }}
),

steps as (
    select *,
           lag(modal_price) over w as prev_price,
           date - lag(date) over w as gap_days,
           max(modal_price) over (partition by market_key, commodity, year order by date
                                  rows between unbounded preceding and current row) as running_peak
    from p
    window w as (partition by market_key, commodity, year order by date)
)

select
    market_key,
    state,
    commodity,
    category,
    year,
    count(*)                                                                as n_report_days,
    round(avg(modal_price), 2)                                              as mean_price,
    round(stddev_samp(modal_price) / nullif(avg(modal_price), 0), 4)        as cv,
    round(avg(abs(modal_price / prev_price - 1)) filter (where gap_days <= 3), 4)
                                                                            as avg_abs_daily_pct_change,
    count(*) filter (where gap_days <= 3)                                   as n_daily_changes,
    round(max(1 - modal_price / running_peak), 4)                           as max_drawdown
from steps
group by market_key, state, commodity, category, year
having count(*) >= 60
