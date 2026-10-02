-- Typed, cleaned, de-duplicated price records (spec 7.2).
-- * names trimmed / whitespace collapsed
-- * district corrections applied (reference.district_corrections)
-- * market names mapped to one canonical name per (state, district) (reference.market_aliases)
-- * dedupe on (arrival_date, state, district, market, commodity, variety, grade),
--   keeping the latest ingested_at (ties: highest raw_id)

with src as (
    select * from {{ source('raw', 'mandi_prices') }}
),

corrections as (
    select * from {{ ref('district_corrections') }}
),

aliases as (
    select state, district_raw, market_raw, district as alias_district, market_canonical
    from {{ ref('market_aliases') }}
),

cleaned as (
    select
        src.raw_id,
        regexp_replace(trim(src.state), '\s+', ' ', 'g')     as state,
        src.district                                           as district_raw,
        src.market                                             as market_raw,
        regexp_replace(trim(src.commodity), '\s+', ' ', 'g') as commodity,
        regexp_replace(trim(coalesce(src.variety, '')), '\s+', ' ', 'g') as variety,
        regexp_replace(trim(coalesce(src.grade, '')), '\s+', ' ', 'g')   as grade,
        src.arrival_date::date                                 as arrival_date,
        src.min_price::numeric                                 as min_price,
        src.max_price::numeric                                 as max_price,
        src.modal_price::numeric                               as modal_price,
        src.commodity_code,
        src.source,
        src.source_file,
        src.period,
        src.ingested_at,
        src.state                                              as state_raw
    from src
),

mapped as (
    select
        c.*,
        coalesce(k.district_corrected, regexp_replace(trim(c.district_raw), '\s+', ' ', 'g'))
                                                               as district,
        k.district_corrected is not null                       as is_district_corrected,
        a.market_canonical                                     as market,
        a.alias_district
    from cleaned c
    left join corrections k
      on k.state = c.state_raw and k.district_raw = c.district_raw and k.market_raw = c.market_raw
    left join aliases a
      on a.state = c.state_raw and a.district_raw = c.district_raw and a.market_raw = c.market_raw
),

ranked as (
    select
        *,
        row_number() over (
            partition by arrival_date, state, district, market, commodity, variety, grade
            order by ingested_at desc, raw_id desc
        ) as dedupe_rank
    from mapped
)

select
    raw_id,
    arrival_date,
    state,
    district,
    market,
    commodity,
    variety,
    grade,
    min_price,
    max_price,
    modal_price,
    commodity_code,
    period,
    source,
    source_file,
    ingested_at,
    district_raw,
    market_raw,
    is_district_corrected,
    alias_district
from ranked
where dedupe_rank = 1
