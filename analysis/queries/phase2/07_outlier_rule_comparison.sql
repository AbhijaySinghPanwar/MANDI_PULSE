-- Why the outlier rule was tuned: outliers per month for Tomato in 2023 under the spec rule
-- (own 30-day history only) vs the tuned rule (must also disagree with same-day state peers).
-- Jun-Sep 2023 is the genuine nationwide tomato spike and the crash that followed it.
select
    to_char(arrival_date, 'YYYY-MM')                                       as month,
    count(*)                                                                as n_rows,
    count(*) filter (where flag_outlier_temporal)                           as n_outlier_spec_rule,
    count(*) filter (where flag_outlier)                                    as n_outlier_tuned,
    round(100.0 * count(*) filter (where flag_outlier_temporal) / count(*), 1) as pct_spec_rule,
    round(100.0 * count(*) filter (where flag_outlier) / count(*), 1)       as pct_tuned,
    round(percentile_cont(0.5) within group (order by modal_price)::numeric) as median_modal
from intermediate.int_price_flags
where commodity = 'Tomato' and arrival_date between '2023-01-01' and '2023-12-31'
group by 1
order by 1;
