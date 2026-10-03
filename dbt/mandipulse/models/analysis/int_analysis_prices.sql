-- Base for every Phase 3 mart: one price per market x commodity x day.
--   * period = analysis_period ('main': 2018-01-01 .. 2025-10-31)
--   * valid rows only (fact_daily_price), markets with has_valid_data
--   * include_suspect_low = false (default): suspect-low rows excluded (modal_price);
--     true (sensitivity build into marts_incl_suspect): modal_price_incl_suspect
{{ config(indexes=[
    {'columns': ['market_key', 'commodity_key', 'date']},
    {'columns': ['commodity_key', 'date']},
]) }}

select
    f.date_key,
    d.date,
    f.market_key,
    m.state,
    m.district,
    m.market,
    m.town_key,
    m.geo_precision,
    f.commodity_key,
    c.commodity,
    c.category,
    {% if var('include_suspect_low') %}
    f.modal_price_incl_suspect as modal_price
    {% else %}
    f.modal_price
    {% endif %}
from {{ ref('fact_daily_price') }} f
join {{ ref('dim_date') }} d using (date_key)
join {{ ref('dim_market') }} m using (market_key)
join {{ ref('dim_commodity') }} c using (commodity_key)
where f.period = '{{ var("analysis_period") }}'
  and m.has_valid_data
  {% if var('include_suspect_low') %}
  and f.modal_price_incl_suspect is not null
  {% else %}
  and f.modal_price is not null
  {% endif %}
