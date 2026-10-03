-- Crash label (spec 9.2) per market x commodity x day, computed ONLY from days with data:
--   crash = 1 if min(price over the next crash_horizon_days calendar days)
--               < crash_drop_ratio x median(price over the last crash_lookback_days days, incl. today)
-- Windows are calendar windows; only days on which the market reported are used.
-- A label is NULL (unknown) when the lookback has < 5 report days, the horizon has no report,
-- or the horizon runs past the end of the analysis period.
-- Uses future prices by design: for analysis (Q3) and as the Phase 4 target, never as a feature.
{{ config(indexes=[{'columns': ['commodity_key', 'date']}]) }}

with p as (
    select market_key, commodity_key, commodity, state, date, modal_price
    from {{ ref('int_analysis_prices') }}
),

future as (
    select
        p.*,
        min(modal_price) over w_future   as future_min,
        count(*) over w_future           as n_future_obs,
        max(date) over ()                as last_date
    from p
    window w_future as (
        partition by market_key, commodity_key order by date
        range between interval '1 day' following and interval '{{ var("crash_horizon_days") }} days' following
    )
)

select
    f.market_key,
    f.commodity_key,
    f.commodity,
    f.state,
    f.date,
    f.modal_price,
    lb.lookback_median,
    lb.n_lookback_obs,
    f.future_min,
    f.n_future_obs,
    case
        when lb.n_lookback_obs < 5 or f.n_future_obs = 0
             or f.date > f.last_date - {{ var('crash_horizon_days') }} then null
        else f.future_min < {{ var('crash_drop_ratio') }} * lb.lookback_median
    end as is_crash
from future f
cross join lateral (
    select
        percentile_cont(0.5) within group (order by q.modal_price) as lookback_median,
        count(*)                                                   as n_lookback_obs
    from {{ ref('int_analysis_prices') }} q
    where q.market_key = f.market_key
      and q.commodity_key = f.commodity_key
      and q.date > f.date - {{ var('crash_lookback_days') }}
      and q.date <= f.date
) lb
