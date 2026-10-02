-- The 30 most extreme outlier flags (ratio of modal to its trailing 30-day median), for review.
select
    state, district, market, commodity, arrival_date, variety,
    min_price, max_price, modal_price,
    round(rolling_median::numeric, 0)                          as rolling_median_30d,
    rolling_n_obs,
    round((modal_price / rolling_median::numeric), 2)         as ratio_to_median,
    flag_unit_suspect
from intermediate.int_price_flags
where flag_outlier
order by abs(ln(modal_price / rolling_median::numeric)) desc
limit 30;
