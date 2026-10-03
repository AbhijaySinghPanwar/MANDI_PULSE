-- Robustness of every Phase 3 headline number (Q1-Q5), main period 2018-01-01..2025-10-31.
-- Three versions:
--   a_default                 headline: valid rows, suspect-low excluded, all geocode precisions
--   b_no_centroid             pairs only where BOTH markets were geocoded at market level
--                             (Q3/Q5 have no pairs: markets located only by district centroid are dropped)
--   c_incl_suspect_low        suspect-low rows included (schema marts_incl_suspect)
-- Output: question, metric, commodity, version, value.

with
-- ---------------- Q1: same-day gap between pairs <= 100 km ----------------
q1 as (
    select 'Q1' as question, commodity, 'a_default' as version, pct_gap, abs_gap
    from marts.mart_price_spread
    union all
    select 'Q1', commodity, 'b_no_centroid', pct_gap, abs_gap
    from marts.mart_price_spread where pair_precision = 'both_market'
    union all
    select 'Q1', commodity, 'c_incl_suspect_low', pct_gap, abs_gap
    from marts_incl_suspect.mart_price_spread
),
q1_out as (
    select question, 'median_pct_gap' as metric, commodity, version,
           round(100 * percentile_cont(0.5) within group (order by pct_gap)::numeric, 1) as value
    from q1 group by 1, 3, 4
    union all
    select question, 'median_abs_gap_rs_qtl', commodity, version,
           round(percentile_cont(0.5) within group (order by abs_gap)::numeric, 0)
    from q1 group by 1, 3, 4
    union all
    select question, 'p90_pct_gap', commodity, version,
           round(100 * percentile_cont(0.9) within group (order by pct_gap)::numeric, 1)
    from q1 group by 1, 3, 4
),

-- ---------------- Q2: opportunity rate after transport cost ----------------
q2 as (
    select commodity, scenario, 'a_default' as version,
           has_opportunity as opp, best_opportunity_gain as gain
    from marts.mart_opportunity_market_day
    union all
    select commodity, scenario, 'b_no_centroid',
           has_opportunity_market_precision, null::numeric
    from marts.mart_opportunity_market_day where n_neighbors_market_precision > 0
    union all
    select commodity, scenario, 'c_incl_suspect_low', has_opportunity, best_opportunity_gain
    from marts_incl_suspect.mart_opportunity_market_day
),
q2_all as (
    select commodity, scenario, version, opp, gain from q2
    union all
    select 'All', scenario, version, opp, gain from q2
),
q2_out as (
    select 'Q2' as question, 'opportunity_rate_pct_' || scenario as metric, commodity, version,
           round(100.0 * avg(opp::int), 1) as value
    from q2_all group by scenario, commodity, version
    union all
    select 'Q2', 'median_best_gain_rs_qtl_mid', commodity, version,
           round(percentile_cont(0.5) within group (order by gain)::numeric, 0)
    from q2_all where scenario = 'mid' and opp and version <> 'b_no_centroid'
    group by commodity, version
),

-- ---------------- Q3: crashes and seasonality ----------------
q3 as (
    select l.commodity, extract(month from l.date)::int as month, l.is_crash, 'a_default' as version
    from marts.int_crash_labels l where l.is_crash is not null
    union all
    select l.commodity, extract(month from l.date)::int, l.is_crash, 'b_no_centroid'
    from marts.int_crash_labels l
    join marts.dim_market m using (market_key)
    where l.is_crash is not null and m.geo_precision = 'market'
    union all
    select l.commodity, extract(month from l.date)::int, l.is_crash, 'c_incl_suspect_low'
    from marts_incl_suspect.int_crash_labels l where l.is_crash is not null
),
q3_month as (
    select commodity, version, month, avg(is_crash::int) as rate,
           row_number() over (partition by commodity, version order by avg(is_crash::int) desc) as rk
    from q3 group by 1, 2, 3
),
q3_out as (
    select 'Q3' as question, 'crash_rate_pct_all_months' as metric, commodity, version,
           round(100.0 * avg(is_crash::int), 2) as value
    from q3 group by 3, 4
    union all
    select 'Q3', 'crash_rate_pct_peak_month', commodity, version, round(100 * rate, 2)
    from q3_month where rk = 1
    union all
    select 'Q3', 'peak_crash_month_number', commodity, version, month
    from q3_month where rk = 1
),

-- ---------------- Q4: price-trapped districts ----------------
q4 as (
    select commodity, 'a_default' as version, district, state, is_price_trapped as trapped
    from marts.mart_district_access
    union all
    select commodity, 'b_no_centroid', district, state, is_price_trapped_market_precision
    from marts.mart_district_access
    union all
    select commodity, 'c_incl_suspect_low', district, state, is_price_trapped
    from marts_incl_suspect.mart_district_access
),
q4_out as (
    select 'Q4' as question, 'n_trapped_district_crop' as metric, commodity, version,
           count(*) filter (where trapped)::numeric as value
    from q4 group by 3, 4
    union all
    select 'Q4', 'n_trapped_district_crop', 'All', version, count(*) filter (where trapped)
    from q4 group by 4
    union all
    select 'Q4', 'n_distinct_trapped_districts', 'All', version,
           count(distinct state || '|' || district) filter (where trapped)
    from q4 group by 4
    union all
    select 'Q4', 'n_district_crop_total', 'All', version, count(*)
    from q4 group by 4
),

-- ---------------- Q5: volatility ----------------
q5 as (
    select commodity, cv, avg_abs_daily_pct_change, 'a_default' as version
    from marts.mart_volatility
    union all
    select v.commodity, v.cv, v.avg_abs_daily_pct_change, 'b_no_centroid'
    from marts.mart_volatility v join marts.dim_market m using (market_key)
    where m.geo_precision = 'market'
    union all
    select commodity, cv, avg_abs_daily_pct_change, 'c_incl_suspect_low'
    from marts_incl_suspect.mart_volatility
),
q5_out as (
    select 'Q5' as question, 'median_cv' as metric, commodity, version,
           round(percentile_cont(0.5) within group (order by cv)::numeric, 3) as value
    from q5 group by 3, 4
    union all
    select 'Q5', 'median_avg_abs_daily_change_pct', commodity, version,
           round(100 * percentile_cont(0.5) within group (order by avg_abs_daily_pct_change)::numeric, 1)
    from q5 group by 3, 4
)

select * from q1_out
union all select * from q2_out
union all select * from q3_out
union all select * from q4_out
union all select * from q5_out
order by question, metric, commodity, version;
