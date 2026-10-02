-- Spec 7.7: no market may appear with more than one coordinate pair, both in the geocode
-- cache (for current canonical markets) and in dim_market.
with current_markets as (
    select distinct state, district, market from {{ ref('stg_mandi_prices') }}
),
cache as (
    select g.state, g.district, g.market,
           count(distinct (g.latitude, g.longitude)) as n_pairs
    from {{ ref('market_geo') }} g
    join current_markets m using (state, district, market)
    group by 1, 2, 3
),
dim as (
    select state, district, market, count(distinct (latitude, longitude)) as n_pairs
    from {{ ref('dim_market') }}
    group by 1, 2, 3
)
select 'cache' as where_found, * from cache where n_pairs > 1
union all
select 'dim_market', * from dim where n_pairs > 1
