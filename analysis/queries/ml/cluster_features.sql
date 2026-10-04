-- Model C (spec 9.3) inputs: one row per market x commodity series with >= 180 report days in
-- the main period. Built from the sensitivity schema marts_incl_suspect so that the 22
-- suspect-low series are clustered too (is_suspect_series marks them).
--   cv                    std / mean of daily modal prices
--   price_index           mean of (market price / same-day state median)
--   report_freq           report days / days between first and last report
--   seasonal_amplitude    (max - min) of calendar-month medians / overall median
--   crash_rate            share of labelled days that are crashes (sustained definition)
--   n_markets_within_50km distinct OTHER town locations with data for the crop within 50 km
with p as (
    select market_key, commodity_key, commodity, state, date, modal_price
    from marts_incl_suspect.int_analysis_prices
),
series as (
    select market_key, commodity_key, commodity, state,
           count(*)                                            as n_report_days,
           stddev_samp(modal_price) / avg(modal_price)         as cv,
           count(*)::float / (max(date) - min(date) + 1)       as report_freq,
           percentile_cont(0.5) within group (order by modal_price) as overall_median
    from p
    group by 1, 2, 3, 4
    having count(*) >= 180
),
state_day as (
    select state, commodity_key, date,
           percentile_cont(0.5) within group (order by modal_price) as state_median
    from p group by 1, 2, 3
),
idx as (
    select p.market_key, p.commodity_key, avg(p.modal_price / s.state_median) as price_index
    from p join state_day s using (state, commodity_key, date)
    group by 1, 2
),
monthly as (
    select market_key, commodity_key, extract(month from date) as month,
           percentile_cont(0.5) within group (order by modal_price) as month_median
    from p group by 1, 2, 3
),
season as (
    select m.market_key, m.commodity_key,
           (max(m.month_median) - min(m.month_median)) / max(s.overall_median) as seasonal_amplitude
    from monthly m join series s using (market_key, commodity_key)
    group by 1, 2
),
crash as (
    select market_key, commodity_key, avg(is_crash::int) as crash_rate
    from marts_incl_suspect.int_crash_labels where is_crash is not null
    group by 1, 2
),
loc as (
    select distinct p.market_key, p.commodity_key, m.town_key, m.latitude, m.longitude
    from p join marts.dim_market m using (market_key)
),
near as (
    select a.market_key, a.commodity_key, count(distinct b.town_key) as n_markets_within_50km
    from loc a
    left join loc b
      on b.commodity_key = a.commodity_key
     and b.town_key <> a.town_key
     and abs(b.latitude - a.latitude) <= 50 / 111.0
     and 2 * 6371.0088 * asin(sqrt(power(sin(radians(b.latitude - a.latitude) / 2), 2)
         + cos(radians(a.latitude)) * cos(radians(b.latitude))
         * power(sin(radians(b.longitude - a.longitude) / 2), 2))) <= 50
    group by 1, 2
),
suspect as (
    select distinct m.market_key, c.commodity_key
    from intermediate.int_price_flags f
    join marts.dim_market m on m.state = f.state and m.district = f.district and m.market = f.market
    join marts.dim_commodity c on c.commodity = f.commodity
    where f.flag_persistent_low
)
select
    s.market_key, s.commodity_key, s.commodity, s.state, dm.district, dm.market,
    s.n_report_days,
    round(s.cv::numeric, 4)                    as cv,
    round(i.price_index::numeric, 4)           as price_index,
    round(s.report_freq::numeric, 4)           as report_freq,
    round(se.seasonal_amplitude::numeric, 4)   as seasonal_amplitude,
    round(coalesce(c.crash_rate, 0)::numeric, 4) as crash_rate,
    coalesce(n.n_markets_within_50km, 0)       as n_markets_within_50km,
    (sp.market_key is not null)                as is_suspect_series
from series s
join idx i using (market_key, commodity_key)
join season se using (market_key, commodity_key)
left join crash c using (market_key, commodity_key)
left join near n using (market_key, commodity_key)
left join suspect sp using (market_key, commodity_key)
join marts.dim_market dm using (market_key)
order by s.commodity, s.state, dm.district, dm.market;
