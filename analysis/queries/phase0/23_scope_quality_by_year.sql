-- Per state x year (all three crops): share of rows with min or max price <= 0 and with min > max.
-- Shows that Uttar Pradesh's zero-price placeholders are concentrated before 2018.
select
    state, year(arrival_date) as year,
    count(*)                                                 as n_rows,
    count(*) filter (where min_price <= 0 or max_price <= 0) as n_min_or_max_nonpositive,
    round(100.0 * count(*) filter (where min_price <= 0 or max_price <= 0) / count(*), 2)
                                                             as pct_min_or_max_nonpositive,
    count(*) filter (where min_price > max_price)            as n_min_gt_max
from scope_prices
group by all
order by state, year;
