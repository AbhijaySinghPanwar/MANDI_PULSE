-- Q4. Per district x commodity:
--   n_markets_within_50km  distinct TOWN locations (town_key) with valid data for the commodity
--                          within near_radius_km of the district centroid (any precision)
--   avg_price_index        mean over days of (district median price / state median price that day)
--   opportunity_rate       share of the district's market-days (mid scenario) with >= 1 profitable
--                          destination within 100 km
--   is_price_trapped       n_markets_within_50km <= trapped_max_markets AND
--                          avg_price_index < trapped_max_price_index
-- *_market_precision columns: the same using only market-level geocodes / both_market pairs.

with towns as (
    -- town locations with valid data for the commodity (cross-state neighbours count too)
    select distinct p.town_key, p.geo_precision, p.commodity, mk.latitude, mk.longitude
    from {{ ref('int_analysis_prices') }} p
    join {{ ref('dim_market') }} mk using (market_key)
),

districts as (
    select distinct p.state, p.district, p.commodity, g.latitude, g.longitude
    from {{ ref('int_analysis_prices') }} p
    join {{ ref('district_geo') }} g on g.state = p.state and g.district = p.district
),

near as (
    select
        d.state, d.district, d.commodity,
        count(distinct t.town_key)                                                as n_towns,
        count(distinct t.town_key) filter (where t.geo_precision = 'market')      as n_towns_market_precision
    from districts d
    join towns t
      on t.commodity = d.commodity
     and abs(t.latitude - d.latitude) <= {{ var('near_radius_km') }} / 111.0
     and {{ haversine_km('d.latitude', 'd.longitude', 't.latitude', 't.longitude') }}
         <= {{ var('near_radius_km') }}
    group by 1, 2, 3
),

district_day as (
    select state, district, commodity, date,
           percentile_cont(0.5) within group (order by modal_price) as district_median
    from {{ ref('int_analysis_prices') }}
    group by 1, 2, 3, 4
),

state_day as (
    select state, commodity, date,
           percentile_cont(0.5) within group (order by modal_price) as state_median
    from {{ ref('int_analysis_prices') }}
    group by 1, 2, 3
),

price_index as (
    select d.state, d.district, d.commodity,
           avg(d.district_median / s.state_median) as avg_price_index,
           count(*)                                as n_days
    from district_day d
    join state_day s using (state, commodity, date)
    group by 1, 2, 3
),

opps as (
    select m.state, m.district, o.commodity,
           count(*)                                                     as n_market_days,
           avg(o.has_opportunity::int)                                  as opportunity_rate,
           avg(o.has_opportunity_market_precision::int)
               filter (where o.n_neighbors_market_precision > 0)        as opportunity_rate_market_precision
    from {{ ref('mart_opportunity_market_day') }} o
    join {{ ref('dim_market') }} m on m.market_key = o.home_market_key
    where o.scenario = 'mid'
    group by 1, 2, 3
)

select
    pi.state,
    pi.district,
    pi.commodity,
    coalesce(n.n_towns, 0)                                       as n_markets_within_50km,
    coalesce(n.n_towns_market_precision, 0)                      as n_markets_within_50km_market_precision,
    round(pi.avg_price_index::numeric, 3)                        as avg_price_index,
    pi.n_days                                                    as n_price_days,
    o.n_market_days                                              as n_opportunity_market_days,
    round(o.opportunity_rate::numeric, 4)                        as opportunity_rate,
    round(o.opportunity_rate_market_precision::numeric, 4)       as opportunity_rate_market_precision,
    (coalesce(n.n_towns, 0) <= {{ var('trapped_max_markets') }}
     and pi.avg_price_index < {{ var('trapped_max_price_index') }}) as is_price_trapped,
    (coalesce(n.n_towns_market_precision, 0) <= {{ var('trapped_max_markets') }}
     and pi.avg_price_index < {{ var('trapped_max_price_index') }}) as is_price_trapped_market_precision
from price_index pi
left join near n using (state, district, commodity)
left join opps o using (state, district, commodity)
