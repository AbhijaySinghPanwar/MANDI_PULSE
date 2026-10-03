-- Q3. Crash rate (%) per commodity x state x month, for the heatmap.
select commodity, state, month, month_name,
       round(100 * crash_rate, 2) as crash_rate_pct, n_labelled_days, price_index
from marts.mart_seasonality
order by commodity, state, month;
