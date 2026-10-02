-- Totals for 08: valid rows > 3x from the same-day state median, by state x commodity.
select
    state, commodity,
    count(*) filter (where is_valid)                                         as n_valid,
    count(*) filter (where is_valid and dev_state_day > ln(3))               as n_far_from_state,
    round(100.0 * count(*) filter (where is_valid and dev_state_day > ln(3))
          / nullif(count(*) filter (where is_valid), 0), 2)                  as pct_far_from_state,
    count(*) filter (where is_valid and dev_state_day > ln(3)
                     and modal_price < state_median)                         as n_below_state
from intermediate.int_price_flags
group by 1, 2
order by 1, 2;
