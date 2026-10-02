-- Staging may only remove rows that duplicate another row's dedupe key, never whole keys:
-- every distinct dedupe key in raw (after district corrections + aliases, with the same name
-- cleaning as staging) must survive as exactly one staging row.
with raw_keys as (
    select count(*) as n
    from (
        select distinct
            r.arrival_date,
            a.state,
            a.district,
            a.market_canonical,
            regexp_replace(trim(r.commodity), '\s+', ' ', 'g'),
            regexp_replace(trim(coalesce(r.variety, '')), '\s+', ' ', 'g'),
            regexp_replace(trim(coalesce(r.grade, '')), '\s+', ' ', 'g')
        from {{ source('raw', 'mandi_prices') }} r
        join {{ ref('market_aliases') }} a
          on a.state = r.state and a.district_raw = r.district and a.market_raw = r.market
    ) k
),
stg as (select count(*) as n from {{ ref('stg_mandi_prices') }})
select raw_keys.n as raw_distinct_keys, stg.n as staging_rows
from raw_keys, stg
where raw_keys.n <> stg.n
