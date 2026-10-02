-- One row per market x commodity x day (spec 7.4), from VALID rows only.
-- Varieties and grades are aggregated: median of modal prices, lowest min, highest max.
-- Gaps are NOT filled: a day without a valid report has no row.

select
    state,
    district,
    market,
    commodity,
    arrival_date,
    percentile_cont(0.5) within group (order by modal_price)::numeric(12, 2) as modal_price,
    min(min_price)                                                          as min_price,
    max(max_price)                                                          as max_price,
    count(distinct variety)                                                 as n_varieties,
    count(*)                                                                as n_rows,
    max(period)                                                             as period,
    string_agg(distinct source, ',' order by source)                        as source
from {{ ref('int_price_flags') }}
where is_valid
group by state, district, market, commodity, arrival_date
