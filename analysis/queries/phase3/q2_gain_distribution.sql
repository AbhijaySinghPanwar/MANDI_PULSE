-- Q2. Distribution of the best gain on opportunity market-days (mid scenario), Rs/qtl bins of 100
-- (the last bin collects everything >= Rs 2000).
select
    commodity,
    least(floor(best_opportunity_gain / 100) * 100, 2000)::int  as gain_bin_start_rs_qtl,
    count(*)                                                    as n_market_days
from marts.mart_opportunity_market_day
where scenario = 'mid' and has_opportunity
group by 1, 2
order by 1, 2;
