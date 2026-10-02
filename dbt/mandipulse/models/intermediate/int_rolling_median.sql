-- Trailing rolling median of the daily baseline price per market x commodity:
-- median over report days in [date - window, date - 1]. The current day is excluded so a
-- price is never compared against itself.

select
    b.series_id,
    b.state,
    b.district,
    b.market,
    b.commodity,
    b.arrival_date,
    r.median_prior    as rolling_median,
    r.n_obs_prior     as rolling_n_obs
from {{ ref('int_daily_baseline') }} b
cross join lateral (
    select
        percentile_cont(0.5) within group (order by p.baseline_modal) as median_prior,
        count(*)                                                       as n_obs_prior
    from {{ ref('int_daily_baseline') }} p
    where p.series_id = b.series_id
      and p.arrival_date >= b.arrival_date - {{ var('outlier_window_days') }}
      and p.arrival_date < b.arrival_date
) r
