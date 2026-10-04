-- Q2 robustness version (d): opportunities from SAME-VARIETY comparisons only.
-- A home market and a destination within spread_radius_km are compared only on days when both
-- report the same (named) variety; costs and the opportunity rule are the same as in
-- int_directed_comparisons. One row per home market x commodity x date x scenario.

with pairs as (
    select pair_key, market_key_a, market_key_b, road_km_est, pair_precision
    from {{ ref('int_market_pairs') }}
    where road_km_est <= {{ var('spread_radius_km') }}
),

both_directions as (
    select pair_key, market_key_a as home_market_key, market_key_b as dest_market_key, road_km_est
    from pairs
    union all
    select pair_key, market_key_b, market_key_a, road_km_est
    from pairs
),

comparisons as (
    select
        p.home_market_key, p.dest_market_key, p.road_km_est,
        h.commodity_key, h.commodity, h.variety, h.date,
        h.modal_price as price_home,
        d.modal_price as price_dest
    from both_directions p
    join {{ ref('int_variety_prices') }} h on h.market_key = p.home_market_key
    join {{ ref('int_variety_prices') }} d
      on d.market_key = p.dest_market_key
     and d.commodity_key = h.commodity_key
     and d.variety = h.variety
     and d.date = h.date
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

gains as (
    select
        c.home_market_key, c.commodity_key, c.commodity, c.date, s.scenario,
        c.price_dest - (c.road_km_est * s.cost_per_qtl_km + s.fixed_cost_per_qtl)
            - c.price_dest * s.fee_pct - c.price_home                   as gain,
        c.price_home
    from comparisons c
    cross join scenarios s
)

select
    home_market_key,
    commodity_key,
    commodity,
    date,
    scenario,
    count(*)                                                                as n_comparisons,
    count(*) filter (where gain >= {{ var('min_gain_abs') }}
                       and gain / price_home >= {{ var('min_gain_pct') }})  as n_opportunities,
    bool_or(gain >= {{ var('min_gain_abs') }}
            and gain / price_home >= {{ var('min_gain_pct') }})             as has_opportunity
from gains
group by home_market_key, commodity_key, commodity, date, scenario
