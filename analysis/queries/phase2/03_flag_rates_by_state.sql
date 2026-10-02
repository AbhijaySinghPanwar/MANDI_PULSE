-- Quality-flag rates per state x commodity (2018 onward, all periods).
select
    state, commodity,
    count(*)                                                                 as n_rows,
    round(100.0 * count(*) filter (where flag_nonpositive) / count(*), 2)   as pct_nonpositive,
    round(100.0 * count(*) filter (where flag_order) / count(*), 2)         as pct_order,
    round(100.0 * count(*) filter (where flag_outlier) / count(*), 2)       as pct_outlier,
    round(100.0 * count(*) filter (where flag_unit_suspect) / count(*), 2)  as pct_unit_suspect,
    round(100.0 * count(*) filter (where not is_valid) / count(*), 2)       as pct_invalid
from intermediate.int_price_flags
group by 1, 2
order by 1, 2;
