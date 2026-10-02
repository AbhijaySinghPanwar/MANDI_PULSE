-- How flags co-occur on invalid rows (each invalid row counted once, by its flag combination).
select
    flag_nonpositive, flag_order, flag_outlier, flag_unit_suspect,
    count(*) as n_rows
from intermediate.int_price_flags
where not is_valid
group by 1, 2, 3, 4
order by n_rows desc;
