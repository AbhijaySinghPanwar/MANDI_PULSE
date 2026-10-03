-- Sanity: are opportunities ACTIONABLE? A farmer only knows earlier prices. For each directed
-- pair x commodity (mid scenario), take comparison days whose previous comparison was <= 3 days
-- earlier. If the previous comparison was an opportunity ("signal"), how often is today's also an
-- opportunity, and what is today's realised gain?
with c as (
    select commodity, home_market_key, dest_market_key, date, gain, is_opportunity,
           lag(is_opportunity) over w as prev_is_opportunity,
           date - lag(date) over w    as days_since_prev
    from marts.int_directed_comparisons
    where scenario = 'mid'
    window w as (partition by commodity, home_market_key, dest_market_key order by date)
)
select
    commodity,
    count(*) filter (where prev_is_opportunity)                                     as n_signals,
    round(100.0 * avg(is_opportunity::int) filter (where prev_is_opportunity), 1)   as pct_signal_still_opportunity,
    round(100.0 * avg((gain > 0)::int) filter (where prev_is_opportunity), 1)       as pct_signal_gain_positive,
    round(percentile_cont(0.5) within group (order by gain) filter (where prev_is_opportunity)::numeric)
                                                                                    as median_realised_gain_after_signal,
    round(percentile_cont(0.5) within group (order by gain) filter (where is_opportunity)::numeric)
                                                                                    as median_gain_ex_post
from c
where days_since_prev <= 3
group by 1
order by 1;
