-- One row per canonical market (state x district x canonical name).
-- Coordinates: geocode cache (reference.market_geo); manual overrides win (geo_precision 'manual').
-- town_key groups markets with identical coordinates (e.g. 'Betul' and 'Betul (F&V)' both resolve
-- to Betul town), so later analyses don't treat same-town yards as "another mandi".
-- has_valid_data = false: no valid daily price at all (e.g. every row flagged); such markets are
-- excluded from all analysis.

with markets as (
    select distinct state, district, market
    from {{ ref('stg_mandi_prices') }}
),

geo as (
    select g.state, g.district, g.market,
           coalesce(o.latitude, g.latitude)                              as latitude,
           coalesce(o.longitude, g.longitude)                            as longitude,
           case when o.market is not null then 'manual' else g.geo_precision end as geo_precision
    from {{ ref('market_geo') }} g
    left join {{ ref('market_geo_overrides') }} o
      on o.state = g.state and o.district = g.district and o.market = g.market
),

activity as (
    select state, district, market,
           min(arrival_date)             as first_report_date,
           max(arrival_date)             as last_report_date,
           count(distinct arrival_date)  as n_report_days
    from {{ ref('int_daily_prices') }}
    group by state, district, market
),

joined as (
    select
        md5(m.state || '|' || m.district || '|' || m.market)            as market_key,
        m.market,
        m.district,
        m.state,
        g.latitude,
        g.longitude,
        coalesce(g.geo_precision, 'not_found')                           as geo_precision,
        case when g.latitude is not null
             then md5(round(g.latitude::numeric, 6)::text || ',' || round(g.longitude::numeric, 6)::text)
        end                                                              as town_key,
        a.first_report_date,
        a.last_report_date,
        coalesce(a.n_report_days, 0)                                     as n_report_days,
        coalesce(a.n_report_days, 0) > 0                                 as has_valid_data
    from markets m
    left join geo g on g.state = m.state and g.district = m.district and g.market = m.market
    left join activity a on a.state = m.state and a.district = m.district and a.market = m.market
)

select
    *,
    count(*) over (partition by town_key) as n_markets_in_town
from joined
