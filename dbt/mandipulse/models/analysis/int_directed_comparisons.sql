-- Every same-day comparison in BOTH directions (home -> destination), for each cost scenario.
--   transport_cost = road_km_est x cost_per_qtl_km + fixed_cost_per_qtl
--   fee_cost       = fee_pct x price_dest   (commission + market fees at the destination,
--                    decision 2026-10-04; fees vary by state, see docs/ASSUMPTIONS.md)
--   net_price_dest = price_dest - transport_cost - fee_cost
--   gain           = net_price_dest - price_home
--   is_opportunity = gain >= min_gain_abs AND gain / price_home >= min_gain_pct
-- Both markets reported that day by construction (built from mart_price_spread).
{{ config(materialized='view') }}

with directed as (
    select date_key, date, commodity_key, commodity, pair_key, road_km_est, pair_precision,
           market_key_a as home_market_key, market_key_b as dest_market_key,
           price_a as price_home, price_b as price_dest
    from {{ ref('mart_price_spread') }}
    union all
    select date_key, date, commodity_key, commodity, pair_key, road_km_est, pair_precision,
           market_key_b, market_key_a, price_b, price_a
    from {{ ref('mart_price_spread') }}
),

scenarios as (
    {% for name, s in var('scenarios').items() %}
    select '{{ name }}'::text as scenario,
           {{ s['cost_per_qtl_km'] }}::numeric as cost_per_qtl_km,
           {{ s['fixed_cost_per_qtl'] }}::numeric as fixed_cost_per_qtl,
           {{ s['fee_pct'] }}::numeric as fee_pct
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
),

costed as (
    select
        d.*,
        s.scenario,
        round(d.road_km_est * s.cost_per_qtl_km + s.fixed_cost_per_qtl, 2) as transport_cost,
        round(d.price_dest * s.fee_pct, 2)                                  as fee_cost
    from directed d
    cross join scenarios s
)

select
    *,
    price_dest - transport_cost - fee_cost                        as net_price_dest,
    price_dest - transport_cost - fee_cost - price_home           as gain,
    round((price_dest - transport_cost - fee_cost - price_home) / price_home, 4) as gain_pct,
    (price_dest - transport_cost - fee_cost - price_home >= {{ var('min_gain_abs') }}
     and (price_dest - transport_cost - fee_cost - price_home) / price_home >= {{ var('min_gain_pct') }})
                                                                  as is_opportunity
from costed
