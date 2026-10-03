-- Sanity: how sensitive is the spec 9.2 crash label to a single low quote?
--   spec       = min(price over next 14 days) < 0.7 x trailing 30-day median (one low report is enough)
--   sustained  = at least 2 report days in the next 14 below 0.7 x trailing median
--   majority   = more than half of the report days in the next 14 below 0.7 x trailing median
-- Same eligibility as int_crash_labels (>= 5 lookback days, >= 1 horizon day, horizon inside period).
with l as (
    select market_key, commodity_key, commodity, date, lookback_median, is_crash
    from marts.int_crash_labels
    where is_crash is not null
),
h as (
    select l.commodity, extract(month from l.date)::int as month, l.is_crash,
           f.n_obs, f.n_below
    from l
    cross join lateral (
        select count(*)                                                    as n_obs,
               count(*) filter (where p.modal_price < 0.7 * l.lookback_median) as n_below
        from marts.int_analysis_prices p
        where p.market_key = l.market_key and p.commodity_key = l.commodity_key
          and p.date > l.date and p.date <= l.date + 14
    ) f
)
select
    commodity,
    count(*)                                                           as n_labelled_days,
    round(100.0 * avg(is_crash::int), 2)                               as crash_rate_spec_pct,
    round(100.0 * avg((n_below >= 2)::int), 2)                         as crash_rate_sustained_2days_pct,
    round(100.0 * avg((n_below > n_obs / 2.0)::int), 2)                as crash_rate_majority_pct,
    round(100.0 * avg(is_crash::int) filter (where month = 12), 2)     as dec_spec_pct,
    round(100.0 * avg((n_below >= 2)::int) filter (where month = 12), 2) as dec_sustained_pct,
    round(100.0 * avg((n_below > n_obs / 2.0)::int) filter (where month = 12), 2) as dec_majority_pct
from h
group by commodity
order by commodity;
