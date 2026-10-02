-- Quality-flag rates by year (all in-scope rows in staging). A row can carry several flags,
-- so the per-flag percentages can add up to more than pct_invalid.
-- n_outlier_spec_rule = outliers under spec 7.3 as written (own-history only), for comparison.
select
    extract(year from arrival_date)::int                                        as year,
    count(*)                                                                     as n_rows,
    count(*) filter (where flag_nonpositive)                                     as n_nonpositive,
    count(*) filter (where flag_order)                                           as n_order,
    count(*) filter (where flag_outlier)                                         as n_outlier,
    count(*) filter (where flag_outlier_temporal)                                as n_outlier_spec_rule,
    count(*) filter (where flag_unit_suspect)                                    as n_unit_suspect,
    count(*) filter (where not is_valid)                                         as n_invalid,
    round(100.0 * count(*) filter (where flag_nonpositive) / count(*), 2)       as pct_nonpositive,
    round(100.0 * count(*) filter (where flag_order) / count(*), 2)             as pct_order,
    round(100.0 * count(*) filter (where flag_outlier) / count(*), 2)           as pct_outlier,
    round(100.0 * count(*) filter (where flag_unit_suspect) / count(*), 2)      as pct_unit_suspect,
    round(100.0 * count(*) filter (where not is_valid) / count(*), 2)           as pct_invalid
from intermediate.int_price_flags
group by 1
union all
select
    null, count(*),
    count(*) filter (where flag_nonpositive), count(*) filter (where flag_order),
    count(*) filter (where flag_outlier), count(*) filter (where flag_outlier_temporal),
    count(*) filter (where flag_unit_suspect),
    count(*) filter (where not is_valid),
    round(100.0 * count(*) filter (where flag_nonpositive) / count(*), 2),
    round(100.0 * count(*) filter (where flag_order) / count(*), 2),
    round(100.0 * count(*) filter (where flag_outlier) / count(*), 2),
    round(100.0 * count(*) filter (where flag_unit_suspect) / count(*), 2),
    round(100.0 * count(*) filter (where not is_valid) / count(*), 2)
from intermediate.int_price_flags
order by 1 nulls last;
