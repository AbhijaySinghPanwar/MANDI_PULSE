-- Variety-level daily prices for the same-variety robustness check of Q2 (decision 2026-10-04).
-- One row per market x commodity x variety x day: median modal of the valid rows (grades pooled).
-- Same scope as int_analysis_prices (analysis period, has_valid_data markets, suspect-low rows
-- excluded unless include_suspect_low). The catch-all variety 'Other' (and blanks) is dropped:
-- "Other" at two markets is no evidence that the same product is being compared.
{{ config(indexes=[{'columns': ['market_key', 'commodity_key', 'variety', 'date']}]) }}

select
    m.market_key,
    c.commodity_key,
    f.commodity,
    f.variety,
    f.arrival_date                                                          as date,
    (percentile_cont(0.5) within group (order by f.modal_price))::numeric(12, 2) as modal_price
from {{ ref('int_price_flags') }} f
join {{ ref('dim_market') }} m
  on m.state = f.state and m.district = f.district and m.market = f.market
join {{ ref('dim_commodity') }} c on c.commodity = f.commodity
where f.is_valid
  and f.period = '{{ var("analysis_period") }}'
  and m.has_valid_data
  and coalesce(f.variety, '') not in ('', 'Other')
  {% if not var('include_suspect_low') %}
  and not f.flag_persistent_low
  {% endif %}
group by m.market_key, c.commodity_key, f.commodity, f.variety, f.arrival_date
