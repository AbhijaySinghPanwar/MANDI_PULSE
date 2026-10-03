-- Sanity: are opportunities (mid scenario) driven by a few destination markets?
-- Cumulative share of all opportunity rows taken by the top destination markets.
with o as (
    select dest_market_key, count(*) as n
    from marts.mart_net_price_opportunities
    where scenario = 'mid'
    group by 1
),
ranked as (
    select n, row_number() over (order by n desc) as rk, count(*) over () as n_dest,
           sum(n) over (order by n desc) as cum, sum(n) over () as total
    from o
)
select 'top 10 destination markets' as slice, round(100.0 * max(cum) filter (where rk = 10) / max(total), 1) as pct_of_opportunities from ranked
union all
select 'top 5% of destination markets', round(100.0 * max(cum) filter (where rk = ceil(n_dest * 0.05)) / max(total), 1) from ranked
union all
select 'top 20% of destination markets', round(100.0 * max(cum) filter (where rk = ceil(n_dest * 0.20)) / max(total), 1) from ranked;
