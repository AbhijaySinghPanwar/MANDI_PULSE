-- Q2 detail: every profitable move (is_opportunity) per scenario, home -> destination, date.
-- Only opportunities are stored (non-opportunities live in the view int_directed_comparisons
-- and are counted in mart_opportunity_market_day). Long format: one row per scenario.
{{ config(indexes=[{'columns': ['scenario', 'commodity_key', 'date']}]) }}

select
    date_key,
    date,
    commodity_key,
    commodity,
    scenario,
    home_market_key,
    dest_market_key,
    pair_key,
    road_km_est,
    pair_precision,
    price_home,
    price_dest,
    transport_cost,
    net_price_dest,
    gain,
    gain_pct,
    is_opportunity
from {{ ref('int_directed_comparisons') }}
where is_opportunity
