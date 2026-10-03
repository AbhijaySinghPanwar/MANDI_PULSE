-- Q3 (how early do warning signs appear?): on crash-labelled days, how far below its trailing
-- 30-day median was the price ALREADY, compared with non-crash days? A rough indicator of how much
-- of the fall is visible in advance (Phase 4 models this properly).
select
    commodity,
    count(*) filter (where is_crash)                                               as n_crash_days,
    round(100 * percentile_cont(0.5) within group (order by modal_price / lookback_median)
          filter (where is_crash)::numeric, 1)                                     as median_price_vs_trailing_median_pct_crash_days,
    round(100 * percentile_cont(0.5) within group (order by modal_price / lookback_median)
          filter (where is_crash = false)::numeric, 1)                             as median_price_vs_trailing_median_pct_other_days
from marts.int_crash_labels
where is_crash is not null
group by 1
order by 1;
