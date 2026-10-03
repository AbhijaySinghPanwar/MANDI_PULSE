-- Sanity: is the opportunity partly a variety/quality mix effect? Each market x commodity gets
-- its dominant variety (most valid rows). Opportunity rate (mid, directed comparisons) for pairs
-- whose dominant varieties are the same vs different.
with dom as (
    select distinct on (state, district, market, commodity)
           md5(state || '|' || district || '|' || market) as market_key, commodity, variety
    from intermediate.int_price_flags
    where is_valid and not flag_persistent_low
    group by state, district, market, commodity, variety
    order by state, district, market, commodity, count(*) desc
)
select
    case when h.variety = d.variety then 'same dominant variety' else 'different dominant variety' end as pair_type,
    c.commodity,
    count(*)                                         as n_comparisons,
    round(100.0 * avg(c.is_opportunity::int), 1)     as pct_opportunity,
    round(percentile_cont(0.5) within group (order by abs(c.price_dest - c.price_home) / c.price_home)::numeric, 3)
                                                     as median_pct_gap
from marts.int_directed_comparisons c
join dom h on h.market_key = c.home_market_key and h.commodity = c.commodity
join dom d on d.market_key = c.dest_market_key and d.commodity = c.commodity
where c.scenario = 'mid'
group by 1, 2
order by 2, 1;
