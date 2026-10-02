-- Row counts at each step, per state x commodity, with every drop broken down by cause.
--   raw_rows                 raw.mandi_prices
--   dedupe_exact_dup         dropped in staging: identical to the kept row in every column
--                            (same raw market name, same prices)
--   dedupe_alias_same_price  dropped in staging: a different raw name of the same canonical
--                            market (e.g. 'X' and 'X APMC') on the same key, same modal price
--   dedupe_other             dropped in staging for any other reason (expected 0)
--   staging_rows             staging.stg_mandi_prices
--   flagged_invalid          rows with >= 1 quality flag (kept in int_price_flags, not in the fact)
--   valid_rows               is_valid rows
--   collapsed_in_daily       valid rows merged into one daily row (several varieties/grades per day)
--   daily_fact_rows          marts.fact_daily_price
with keyed as (
    select
        r.raw_id, r.state, r.commodity, r.market, r.min_price, r.max_price, r.modal_price,
        row_number() over (
            partition by r.arrival_date, a.state, a.district, a.market_canonical,
                         r.commodity, r.variety, r.grade
            order by r.ingested_at desc, r.raw_id desc) as rnk,
        first_value(r.market) over w      as kept_market,
        first_value(r.min_price) over w   as kept_min,
        first_value(r.max_price) over w   as kept_max,
        first_value(r.modal_price) over w as kept_modal
    from raw.mandi_prices r
    join reference.market_aliases a
      on a.state = r.state and a.district_raw = r.district and a.market_raw = r.market
    window w as (
        partition by r.arrival_date, a.state, a.district, a.market_canonical,
                     r.commodity, r.variety, r.grade
        order by r.ingested_at desc, r.raw_id desc)
),
dropped as (
    select state, commodity,
        count(*) filter (where market = kept_market and min_price = kept_min
                           and max_price = kept_max and modal_price = kept_modal) as exact_dup,
        count(*) filter (where market <> kept_market and modal_price = kept_modal) as alias_same_price,
        count(*) filter (where not ((market = kept_market and min_price = kept_min
                                     and max_price = kept_max and modal_price = kept_modal)
                                    or (market <> kept_market and modal_price = kept_modal))) as other
    from keyed
    where rnk > 1
    group by state, commodity
),
raw_counts as (
    select state, commodity, count(*) as raw_rows from raw.mandi_prices group by 1, 2
),
flags as (
    select state, commodity,
           count(*)                         as staging_rows,
           count(*) filter (where not is_valid) as flagged_invalid,
           count(*) filter (where is_valid)     as valid_rows
    from intermediate.int_price_flags
    group by 1, 2
),
daily as (
    select m.state, c.commodity, count(*) as daily_fact_rows
    from marts.fact_daily_price f
    join marts.dim_market m using (market_key)
    join marts.dim_commodity c using (commodity_key)
    group by 1, 2
)
select
    r.state, r.commodity,
    r.raw_rows,
    coalesce(d.exact_dup, 0)                        as dedupe_exact_dup,
    coalesce(d.alias_same_price, 0)                 as dedupe_alias_same_price,
    coalesce(d.other, 0)                            as dedupe_other,
    f.staging_rows,
    f.flagged_invalid,
    f.valid_rows,
    f.valid_rows - dl.daily_fact_rows               as collapsed_in_daily,
    dl.daily_fact_rows,
    r.raw_rows - coalesce(d.exact_dup, 0) - coalesce(d.alias_same_price, 0)
        - coalesce(d.other, 0) - f.staging_rows     as check_raw_to_staging,   -- must be 0
    f.staging_rows - f.flagged_invalid - f.valid_rows as check_flags           -- must be 0
from raw_counts r
join flags f using (state, commodity)
join daily dl using (state, commodity)
left join dropped d using (state, commodity)
order by r.state, r.commodity;
