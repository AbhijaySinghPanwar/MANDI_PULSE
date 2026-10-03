-- All unordered pairs of markets (market_key_a < market_key_b) within max_pair_km (straight line).
-- Excluded (user decision 2026-10-03):
--   * same town_key: same-town yards share coordinates and are not "another mandi"
--   * both markets are district-centroid fallbacks in the same district (distance meaningless)
--   * markets without valid data or coordinates
-- road_km_est = haversine_km x road_factor (documented assumption, spec 7.6).

with m as (
    select market_key, state, district, market, latitude, longitude, geo_precision, town_key
    from {{ ref('dim_market') }}
    where has_valid_data and latitude is not null
),

pairs as (
    select
        a.market_key as market_key_a,
        b.market_key as market_key_b,
        a.state      as state_a,
        b.state      as state_b,
        a.district   as district_a,
        b.district   as district_b,
        a.geo_precision as geo_precision_a,
        b.geo_precision as geo_precision_b,
        {{ haversine_km('a.latitude', 'a.longitude', 'b.latitude', 'b.longitude') }} as haversine_km
    from m a
    join m b
      on a.market_key < b.market_key
     and a.town_key <> b.town_key
     and not (a.geo_precision = 'district_centroid' and b.geo_precision = 'district_centroid'
              and a.state = b.state and a.district = b.district)
     -- cheap bounding box before the exact distance (1 degree latitude ~ 111 km)
     and abs(a.latitude - b.latitude) <= {{ var('max_pair_km') }} / 111.0
)

select
    md5(market_key_a || '|' || market_key_b)                     as pair_key,
    market_key_a,
    market_key_b,
    state_a,
    state_b,
    district_a,
    district_b,
    round(haversine_km::numeric, 2)                              as haversine_km,
    round((haversine_km * {{ var('road_factor') }})::numeric, 2) as road_km_est,
    case
        when geo_precision_a = 'district_centroid' and geo_precision_b = 'district_centroid'
            then 'both_centroid'
        when geo_precision_a = 'district_centroid' or geo_precision_b = 'district_centroid'
            then 'one_centroid'
        else 'both_market'
    end                                                          as pair_precision,
    state_a = state_b                                            as is_same_state
from pairs
where haversine_km <= {{ var('max_pair_km') }}
