-- Q1. Median same-day pct gap by road-distance band (does the gap grow with distance?).
select
    commodity,
    (floor(road_km_est / 20) * 20)::int                                           as road_km_band_start,
    count(*)                                                                      as n_pair_days,
    round(100 * percentile_cont(0.5) within group (order by pct_gap)::numeric, 1) as median_pct_gap,
    round(percentile_cont(0.5) within group (order by abs_gap)::numeric)          as median_abs_gap_rs_qtl
from marts.mart_price_spread
group by 1, 2
order by 1, 2;
