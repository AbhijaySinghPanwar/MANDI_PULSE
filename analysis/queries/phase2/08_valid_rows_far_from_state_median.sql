-- Valid rows whose modal price is > 3x away from the same-day state median (dev_state_day > ln 3).
-- They pass every flag because their OWN history agrees with them, i.e. the whole series is
-- persistently off (possible chronic unit/entry error, or genuinely low-grade produce).
-- Listed per market x commodity for review before Phase 3 (they would look "price-trapped").
select
    state, district, market, commodity,
    count(*)                                        as n_rows,
    min(arrival_date)                               as first_date,
    max(arrival_date)                               as last_date,
    round(avg(modal_price))                         as avg_modal,
    round(avg(state_median)::numeric)               as avg_state_median,
    round(avg(modal_price / state_median::numeric), 2) as avg_ratio_to_state,
    count(*) filter (where modal_price < state_median) as n_below_state
from intermediate.int_price_flags
where is_valid and dev_state_day > ln(3)          -- ln(3) = quality.outlier_log_ratio
group by 1, 2, 3, 4
having count(*) >= 30
order by n_rows desc;
