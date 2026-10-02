-- Whole-archive quality issues by year, to see whether they are concentrated in early years.
select
    year(arrival_date)                                                         as year,
    count(*)                                                                   as n_rows,
    count(*) filter (where min_price <= 0 or max_price <= 0)                   as n_min_or_max_nonpositive,
    count(*) filter (where min_price > max_price)                              as n_min_gt_max,
    count(*) filter (where modal_price < min_price or modal_price > max_price) as n_modal_outside_min_max,
    count(*) filter (where min_price is null or max_price is null
                       or modal_price is null)                                 as n_null_price
from prices
group by all
order by year;
