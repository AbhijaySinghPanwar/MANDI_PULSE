-- Data-quality flags (spec 7.3). Rows are flagged, never deleted; marts filter on is_valid.
--
-- Missing min/max (zero_min_max_as_missing, user decision 2026-10-03): a min or max <= 0 is an
-- old placeholder, so it becomes NULL (raw value kept in min_price_raw / max_price_raw).
-- The row stays valid if its modal price is fine.
--
-- Validity flags (any -> is_valid = false):
--   flag_nonpositive   modal price <= 0 or missing
--   flag_order         modal below a present min, above a present max, or min > max
--   flag_unit_suspect  modal outside [unit_min_per_qtl, unit_max_per_qtl] (Rs/qtl)
--   flag_outlier       tuned rule, see below
--
-- Outlier rule (tuned, as spec 7.3 asks; var outlier_rule):
--   dev_own_history = |ln(modal) - ln(median of this market's previous 30 days)|
--                     (needs >= outlier_min_obs prior report days)
--   dev_state_day   = |ln(modal) - ln(median of the state's markets that day)|
--                     (needs >= outlier_min_state_markets markets that day)
--   'temporal'                   (spec as written): dev_own_history > ln 3
--   'temporal_and_cross_section' (default): dev_own_history > ln 3 AND, when a same-day state
--                                reference exists, dev_state_day > ln 3.
--   The spec rule flagged ~24% of tomato rows in Jul 2023, the genuine nationwide price spike.
--   flag_outlier_temporal keeps the spec-rule result for transparency.
--
-- Suspect flag (NOT part of is_valid; user decision 2026-10-03):
--   flag_persistent_low  valid row more than 3x BELOW the same-day state median, in a
--                        market x commodity series where such days are persistent
--                        (>= persistent_low_min_rows and >= persistent_low_min_share of the
--                        series' days that have a state reference). Analysis excludes these
--                        rows unless include_suspect_low = true. To be cross-checked vs CEDA.

with s as (
    select * from {{ ref('stg_mandi_prices') }}
),

r as (
    select state, district, market, commodity, arrival_date, rolling_median, rolling_n_obs
    from {{ ref('int_rolling_median') }}
),

x as (
    select state, commodity, arrival_date, state_median, n_markets
    from {{ ref('int_state_daily_median') }}
),

prices as (
    select
        s.raw_id, s.arrival_date, s.state, s.district, s.market, s.commodity, s.variety,
        s.grade, s.commodity_code, s.period, s.source, s.source_file, s.ingested_at,
        s.district_raw, s.market_raw, s.is_district_corrected,
        s.min_price as min_price_raw,
        s.max_price as max_price_raw,
        {% if var('zero_min_max_as_missing') %}
        case when s.min_price > 0 then s.min_price end as min_price,
        case when s.max_price > 0 then s.max_price end as max_price,
        {% else %}
        s.min_price,
        s.max_price,
        {% endif %}
        s.modal_price
    from s
),

deviations as (
    select
        p.*,
        (p.min_price_raw <= 0 or p.max_price_raw <= 0) is true            as is_min_max_placeholder,
        r.rolling_median,
        coalesce(r.rolling_n_obs, 0)                                       as rolling_n_obs,
        x.state_median,
        coalesce(x.n_markets, 0)                                           as state_n_markets,
        case when p.modal_price > 0 and r.rolling_n_obs >= {{ var('outlier_min_obs') }}
                  and r.rolling_median > 0
             then abs(ln(p.modal_price) - ln(r.rolling_median::numeric)) end as dev_own_history,
        case when p.modal_price > 0 and x.n_markets >= {{ var('outlier_min_state_markets') }}
                  and x.state_median > 0
             then abs(ln(p.modal_price) - ln(x.state_median::numeric)) end   as dev_state_day
    from prices p
    left join r
      on r.state = p.state and r.district = p.district and r.market = p.market
     and r.commodity = p.commodity and r.arrival_date = p.arrival_date
    left join x
      on x.state = p.state and x.commodity = p.commodity and x.arrival_date = p.arrival_date
),

flagged as (
    select
        *,
        (coalesce(modal_price, 0) <= 0)                                       as flag_nonpositive,
        (modal_price < min_price or modal_price > max_price or min_price > max_price)
            is true                                                           as flag_order,
        (modal_price < {{ var('unit_min_per_qtl') }}
         or modal_price > {{ var('unit_max_per_qtl') }}) is true              as flag_unit_suspect,
        (dev_own_history > {{ var('outlier_log_ratio') }}) is true            as flag_outlier_temporal,
        {% if var('outlier_rule') == 'temporal' %}
        (dev_own_history > {{ var('outlier_log_ratio') }}) is true            as flag_outlier
        {% elif var('outlier_rule') == 'temporal_and_cross_section' %}
        (dev_own_history > {{ var('outlier_log_ratio') }}
         and (dev_state_day is null or dev_state_day > {{ var('outlier_log_ratio') }}))
            is true                                                           as flag_outlier
        {% else %}
        {{ exceptions.raise_compiler_error("unknown outlier_rule: " ~ var('outlier_rule')) }}
        {% endif %}
    from deviations
),

validity as (
    select
        *,
        not (flag_nonpositive or flag_order or flag_outlier or flag_unit_suspect) as is_valid
    from flagged
),

low as (
    select
        *,
        (is_valid and modal_price < state_median
         and dev_state_day > {{ var('persistent_low_log_ratio') }}) is true      as is_low_vs_state
    from validity
),

series as (
    select
        *,
        count(*) filter (where is_low_vs_state)
            over (partition by state, district, market, commodity)               as series_n_low,
        count(*) filter (where is_valid and dev_state_day is not null)
            over (partition by state, district, market, commodity)               as series_n_with_ref
    from low
)

select
    *,
    (is_low_vs_state
     and series_n_low >= {{ var('persistent_low_min_rows') }}
     and series_n_low >= {{ var('persistent_low_min_share') }} * series_n_with_ref) as flag_persistent_low
from series
