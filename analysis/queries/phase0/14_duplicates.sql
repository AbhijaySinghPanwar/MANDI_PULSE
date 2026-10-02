-- Duplicates in scope.
--   exact_dup_rows      extra copies of rows identical in every column
--   key_dup_rows        extra rows sharing the spec 7.2 dedupe key
--                       (date, state, district, market, commodity, variety, grade)
--   n_dup_keys          keys that appear more than once
--   n_conflicting_keys  of those, keys whose copies disagree on modal price
with keyed as (
    select arrival_date, state, district, market, commodity, variety, grade,
           count(*) as n, count(distinct modal_price) as n_modal
    from scope_prices
    group by all
),
exact as (
    select arrival_date, state, district, market, commodity, variety, grade,
           min_price, max_price, modal_price, commodity_code, count(*) as n
    from scope_prices
    group by all
)
select
    (select count(*) from scope_prices)             as n_rows,
    (select sum(n - 1) from exact)                  as exact_dup_rows,
    (select sum(n - 1) from keyed)                  as key_dup_rows,
    (select count(*) from keyed where n > 1)        as n_dup_keys,
    (select count(*) from keyed where n_modal > 1)  as n_conflicting_keys;
