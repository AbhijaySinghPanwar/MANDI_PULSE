-- Markets x crops carrying the suspect flag flag_persistent_low (valid rows > 3x below the
-- same-day state median, persistently). Excluded from headline analysis; TO CROSS-CHECK AGAINST
-- CEDA (does CEDA show the same low prices for these markets and dates?).
with s as (
    select * from intermediate.int_price_flags where flag_persistent_low
),
dominant as (
    select distinct on (state, district, market, commodity)
           state, district, market, commodity, variety, grade, count(*) as n
    from s
    group by state, district, market, commodity, variety, grade
    order by state, district, market, commodity, count(*) desc
)
select
    s.state,
    s.district,
    s.market,
    s.commodity                                                            as crop,
    count(*)                                                               as n_suspect_rows,
    count(distinct s.arrival_date)                                         as n_suspect_days,
    min(s.arrival_date)                                                    as first_date,
    max(s.arrival_date)                                                    as last_date,
    round(percentile_cont(0.5) within group (order by s.modal_price)::numeric)        as median_modal,
    round(percentile_cont(0.5) within group (order by s.state_median)::numeric)       as median_state_median,
    round(percentile_cont(0.5) within group (order by s.modal_price / s.state_median)::numeric, 2)
                                                                           as median_ratio_to_state,
    d.variety                                                              as dominant_variety,
    d.grade                                                                as dominant_grade,
    round(100.0 * d.n / count(*), 0)                                       as pct_dominant_variety_grade,
    'to cross-check against CEDA'                                          as status
from s
join dominant d using (state, district, market, commodity)
group by s.state, s.district, s.market, s.commodity, d.variety, d.grade, d.n
order by n_suspect_days desc;
