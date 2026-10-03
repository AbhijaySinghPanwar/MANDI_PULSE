-- Sanity: is the opportunity structural (the same destination is better on most days) or
-- sporadic day-to-day noise? Directed pairs (mid scenario) bucketed by the share of their
-- comparison days that are opportunities.
with d as (
    select home_market_key, dest_market_key, commodity,
           count(*) as n_days, avg(is_opportunity::int) as opp_share,
           sum(is_opportunity::int) as opp_days
    from marts.int_directed_comparisons
    where scenario = 'mid'
    group by 1, 2, 3
)
select
    case when opp_share < 0.2 then '0-20% of days'
         when opp_share < 0.4 then '20-40% of days'
         when opp_share < 0.6 then '40-60% of days'
         when opp_share < 0.8 then '60-80% of days'
         else '80-100% of days' end                     as pair_profitable_on,
    count(*)                                           as n_directed_pairs,
    sum(n_days)                                        as comparison_days,
    sum(opp_days)                                      as opportunity_days,
    round(100.0 * sum(opp_days) / sum(sum(opp_days)) over (), 1) as pct_of_all_opportunity_days
from d
group by 1
order by 1;
