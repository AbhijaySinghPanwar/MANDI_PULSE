-- Crash label per market x commodity x day, computed ONLY from days with data
-- (spec 9.2 as decided 2026-10-04, option b "sustained"):
--   crash = at least crash_min_days_below report days in the next crash_horizon_days calendar
--           days with price < crash_drop_ratio x median(price over the last crash_lookback_days
--           days, incl. today)
-- is_crash_any keeps the original spec rule (one low report is enough) for transparency.
-- A label is NULL (unknown) when the lookback has < 5 report days, the horizon has no report,
-- or the horizon runs past the end of the analysis period.
-- Uses future prices by design: for analysis (Q3) and as the Phase 4 target, never as a feature.
{{ config(indexes=[{'columns': ['commodity_key', 'date']}]) }}

with p as (
    select market_key, commodity_key, commodity, state, date, modal_price
    from {{ ref('int_analysis_prices') }}
),

lb as (
    select
        p.*,
        max(date) over () as last_date,
        l.lookback_median,
        l.n_lookback_obs
    from p
    cross join lateral (
        select
            percentile_cont(0.5) within group (order by q.modal_price) as lookback_median,
            count(*)                                                   as n_lookback_obs
        from {{ ref('int_analysis_prices') }} q
        where q.market_key = p.market_key
          and q.commodity_key = p.commodity_key
          and q.date > p.date - {{ var('crash_lookback_days') }}
          and q.date <= p.date
    ) l
)

select
    lb.market_key,
    lb.commodity_key,
    lb.commodity,
    lb.state,
    lb.date,
    lb.modal_price,
    lb.lookback_median,
    lb.n_lookback_obs,
    f.future_min,
    f.n_future_obs,
    f.n_future_below,
    case
        when lb.n_lookback_obs < 5 or f.n_future_obs = 0
             or lb.date > lb.last_date - {{ var('crash_horizon_days') }} then null
        else f.n_future_below >= {{ var('crash_min_days_below') }}
    end as is_crash,
    case
        when lb.n_lookback_obs < 5 or f.n_future_obs = 0
             or lb.date > lb.last_date - {{ var('crash_horizon_days') }} then null
        else f.n_future_below >= 1
    end as is_crash_any
from lb
cross join lateral (
    select
        min(q.modal_price)                                                         as future_min,
        count(*)                                                                   as n_future_obs,
        count(*) filter (where q.modal_price < {{ var('crash_drop_ratio') }} * lb.lookback_median)
                                                                                   as n_future_below
    from {{ ref('int_analysis_prices') }} q
    where q.market_key = lb.market_key
      and q.commodity_key = lb.commodity_key
      and q.date > lb.date
      and q.date <= lb.date + {{ var('crash_horizon_days') }}
) f
