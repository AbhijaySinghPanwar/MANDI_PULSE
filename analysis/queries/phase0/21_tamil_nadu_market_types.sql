-- Tamil Nadu since Jul 2024: Uzhavar Sandhai (farmer-to-consumer retail markets) vs other
-- markets, compared with Maharashtra wholesale prices over the same window.
-- Low percentiles near Rs 30-50 in non-Uzhavar TN markets indicate Rs/kg entries.
select
    state, commodity,
    case when market ilike '%uzhavar%' then 'uzhavar_sandhai' else 'other' end as market_type,
    count(distinct district || '|' || market) as n_markets,
    count(*)                                  as n_rows,
    quantile_cont(modal_price, 0.10)          as p10_modal,
    quantile_cont(modal_price, 0.50)          as median_modal,
    quantile_cont(modal_price, 0.90)          as p90_modal,
    count(*) filter (where modal_price < 200) as n_modal_below_200
from scope_prices
where state in ('Tamil Nadu', 'Maharashtra')
  and arrival_date between date '2024-07-01' and date '2025-10-31'
group by all
order by state, commodity, market_type;
