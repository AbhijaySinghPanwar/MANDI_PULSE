-- Daily reference price per market x commodity, used only for the outlier flag.
-- Built from rows whose prices are plausible (modal > 0 and inside the unit bounds), so that
-- obvious entry errors do not distort the rolling median they are compared against.
-- The index makes the 30-day lateral lookup in int_rolling_median fast (dbt-postgres recreates
-- it on every rebuild; a fixed-name post-hook index was silently skipped on rebuilds).
{{ config(indexes=[{'columns': ['series_id', 'arrival_date']}]) }}

select
    dense_rank() over (order by state, district, market, commodity) as series_id,
    state,
    district,
    market,
    commodity,
    arrival_date,
    percentile_cont(0.5) within group (order by modal_price)        as baseline_modal
from {{ ref('stg_mandi_prices') }}
where modal_price > 0
  and modal_price between {{ var('unit_min_per_qtl') }} and {{ var('unit_max_per_qtl') }}
group by state, district, market, commodity, arrival_date
