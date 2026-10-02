-- One row per market x commodity x day (spec 7.4), from VALID rows only.
-- Varieties and grades are aggregated: median of modal prices, lowest min, highest max.
-- The day's min (max) is set only if EVERY row that day has a min (max); otherwise NULL, so the
-- day's range always contains its median. Gaps are NOT filled: no valid report -> no row.
--
-- Two price sets (user decision 2026-10-03):
--   modal_price / min_price / max_price              valid rows EXCLUDING suspect-low rows
--                                                    (NULL when every valid row that day is suspect)
--   *_incl_suspect                                   all valid rows (sensitivity analysis)

select
    state,
    district,
    market,
    commodity,
    arrival_date,
    (percentile_cont(0.5) within group (order by modal_price)
        filter (where not flag_persistent_low))::numeric(12, 2)          as modal_price,
    case when count(min_price) filter (where not flag_persistent_low)
              = count(*) filter (where not flag_persistent_low)
         then min(min_price) filter (where not flag_persistent_low) end   as min_price,
    case when count(max_price) filter (where not flag_persistent_low)
              = count(*) filter (where not flag_persistent_low)
         then max(max_price) filter (where not flag_persistent_low) end   as max_price,
    (percentile_cont(0.5) within group (order by modal_price))::numeric(12, 2)
                                                                          as modal_price_incl_suspect,
    case when count(min_price) = count(*) then min(min_price) end         as min_price_incl_suspect,
    case when count(max_price) = count(*) then max(max_price) end         as max_price_incl_suspect,
    count(distinct variety)                                               as n_varieties,
    count(*)                                                              as n_rows,
    count(*) filter (where flag_persistent_low)                           as n_suspect_rows,
    bool_and(flag_persistent_low)                                         as is_suspect_low,
    max(period)                                                           as period,
    string_agg(distinct source, ',' order by source)                      as source
from {{ ref('int_price_flags') }}
where is_valid
group by state, district, market, commodity, arrival_date
