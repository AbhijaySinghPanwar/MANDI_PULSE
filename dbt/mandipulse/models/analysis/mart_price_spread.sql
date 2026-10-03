-- Q1. Same-day price gap between market pairs within spread_radius_km (road estimate).
-- One row per pair x commodity x date on which BOTH markets reported (no filling).
--   abs_gap = |price_a - price_b|  (Rs/qtl)
--   pct_gap = abs_gap / lower of the two prices  ("how much more the better market paid")
{{ config(indexes=[{'columns': ['commodity_key', 'date']}, {'columns': ['pair_key']}]) }}

select
    p.pair_key,
    a.date_key,
    a.date,
    a.commodity_key,
    a.commodity,
    p.market_key_a,
    p.market_key_b,
    p.state_a,
    p.state_b,
    p.is_same_state,
    p.road_km_est,
    p.pair_precision,
    a.modal_price                                                     as price_a,
    b.modal_price                                                     as price_b,
    abs(a.modal_price - b.modal_price)                                as abs_gap,
    round(abs(a.modal_price - b.modal_price) / least(a.modal_price, b.modal_price), 4) as pct_gap
from {{ ref('int_market_pairs') }} p
join {{ ref('int_analysis_prices') }} a
  on a.market_key = p.market_key_a
join {{ ref('int_analysis_prices') }} b
  on b.market_key = p.market_key_b
 and b.commodity_key = a.commodity_key
 and b.date = a.date
where p.road_km_est <= {{ var('spread_radius_km') }}
