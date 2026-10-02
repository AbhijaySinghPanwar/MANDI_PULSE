-- Data-quality counts over the whole archive.
select
    count(*)                                                                   as n_rows,
    count(*) filter (where state is null or district is null or market is null
                       or commodity is null)                                   as n_null_names,
    count(*) filter (where variety is null)                                    as n_null_variety,
    count(*) filter (where grade is null)                                      as n_null_grade,
    count(*) filter (where min_price is null or max_price is null
                       or modal_price is null)                                 as n_null_price,
    count(*) filter (where modal_price <= 0)                                   as n_modal_nonpositive,
    count(*) filter (where min_price <= 0)                                     as n_min_nonpositive,
    count(*) filter (where max_price <= 0)                                     as n_max_nonpositive,
    count(*) filter (where min_price > max_price)                              as n_min_gt_max,
    count(*) filter (where modal_price < min_price or modal_price > max_price) as n_modal_outside_min_max
from prices;
