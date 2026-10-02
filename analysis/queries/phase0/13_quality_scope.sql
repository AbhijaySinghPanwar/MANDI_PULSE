-- Data-quality counts for in-scope rows, per commodity x state.
-- Unit bounds (50..20000 Rs/qtl) come from quality.unit_bounds_per_qtl in settings.yaml.
select
    commodity, state,
    count(*)                                                                   as n_rows,
    count(*) filter (where min_price is null or max_price is null
                       or modal_price is null)                                 as n_null_price,
    count(*) filter (where modal_price <= 0)                                   as n_modal_nonpositive,
    count(*) filter (where min_price <= 0 or max_price <= 0)                   as n_min_or_max_nonpositive,
    count(*) filter (where min_price > max_price)                              as n_min_gt_max,
    count(*) filter (where modal_price < min_price or modal_price > max_price) as n_modal_outside_min_max,
    count(*) filter (where modal_price > 0 and modal_price < 50)               as n_modal_below_50,
    count(*) filter (where modal_price > 20000)                                as n_modal_above_20000
from scope_prices
group by all
order by commodity, state;
