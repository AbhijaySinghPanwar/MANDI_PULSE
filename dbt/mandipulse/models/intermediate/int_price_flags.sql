-- Data-quality flags (spec 7.3). Rows are flagged, never deleted; marts filter on is_valid.
--   flag_nonpositive   any of min / max / modal price <= 0 (or missing)
--   flag_order         not (min <= modal <= max)
--   flag_unit_suspect  modal outside [unit_min_per_qtl, unit_max_per_qtl] (Rs/qtl)
--   flag_outlier       see below
--
-- Outlier rule (tuned, as spec 7.3 asks; var outlier_rule):
--   dev_own_history  = |ln(modal) - ln(median of this market's prior 30 days)|
--                      (needs >= outlier_min_obs prior report days)
--   dev_state_day    = |ln(modal) - ln(median of all markets in the state that day)|
--                      (needs >= outlier_min_state_markets markets that day)
--   'temporal'                    (spec as written): dev_own_history > ln 3
--   'temporal_and_cross_section'  (default): dev_own_history > ln 3 AND, when a same-day state
--                                 reference exists, dev_state_day > ln 3.
--   The spec rule flagged ~24% of tomato rows in Jul 2023: the genuine nationwide price spike.
--   Requiring disagreement with same-day peers keeps market-wide moves and still catches
--   single-market entry errors. flag_outlier_temporal keeps the spec-rule result for audit.

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

deviations as (
    select
        s.*,
        r.rolling_median,
        coalesce(r.rolling_n_obs, 0) as rolling_n_obs,
        x.state_median,
        coalesce(x.n_markets, 0)     as state_n_markets,
        case when s.modal_price > 0 and r.rolling_n_obs >= {{ var('outlier_min_obs') }}
                  and r.rolling_median > 0
             then abs(ln(s.modal_price) - ln(r.rolling_median::numeric)) end as dev_own_history,
        case when s.modal_price > 0 and x.n_markets >= {{ var('outlier_min_state_markets') }}
                  and x.state_median > 0
             then abs(ln(s.modal_price) - ln(x.state_median::numeric)) end   as dev_state_day
    from s
    left join r
      on r.state = s.state and r.district = s.district and r.market = s.market
     and r.commodity = s.commodity and r.arrival_date = s.arrival_date
    left join x
      on x.state = s.state and x.commodity = s.commodity and x.arrival_date = s.arrival_date
),

flagged as (
    select
        *,
        (coalesce(min_price, 0) <= 0 or coalesce(max_price, 0) <= 0
         or coalesce(modal_price, 0) <= 0)                                    as flag_nonpositive,
        not (min_price <= modal_price and modal_price <= max_price) is true   as flag_order,
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
)

select
    *,
    not (flag_nonpositive or flag_order or flag_outlier or flag_unit_suspect) as is_valid
from flagged
