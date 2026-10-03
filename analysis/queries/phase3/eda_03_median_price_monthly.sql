-- EDA. Monthly median of daily modal prices per crop (all markets, Rs/qtl).
select date_trunc('month', date)::date as month, commodity,
       round(percentile_cont(0.5) within group (order by modal_price)::numeric) as median_modal_rs_qtl,
       count(*) as n_market_days
from marts.int_analysis_prices
group by 1, 2
order by 1, 2;
