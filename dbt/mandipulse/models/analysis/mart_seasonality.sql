-- Q3. Per commodity x state x calendar month (1-12):
--   median_price      median of all daily market prices in that month (all years)
--   price_index       median over years of (month median / that year's annual median);
--                     > 1 = the month is usually dearer than the year as a whole
--   crash_rate        share of market-days with a known crash label that are crashes (spec 9.2)

with monthly as (
    select commodity, state, extract(year from date)::int as year,
           extract(month from date)::int as month,
           percentile_cont(0.5) within group (order by modal_price) as month_median
    from {{ ref('int_analysis_prices') }}
    group by 1, 2, 3, 4
),

annual as (
    select commodity, state, extract(year from date)::int as year,
           percentile_cont(0.5) within group (order by modal_price) as year_median
    from {{ ref('int_analysis_prices') }}
    group by 1, 2, 3
),

index_by_year as (
    select m.commodity, m.state, m.month, m.month_median / a.year_median as idx
    from monthly m
    join annual a using (commodity, state, year)
),

prices as (
    select commodity, state, extract(month from date)::int as month,
           percentile_cont(0.5) within group (order by modal_price) as median_price,
           count(*) as n_market_days
    from {{ ref('int_analysis_prices') }}
    group by 1, 2, 3
),

crashes as (
    select commodity, state, extract(month from date)::int as month,
           count(*) filter (where is_crash is not null)     as n_labelled_days,
           count(*) filter (where is_crash)                 as n_crash_days
    from {{ ref('int_crash_labels') }}
    group by 1, 2, 3
)

select
    p.commodity,
    c2.category,
    p.state,
    p.month,
    to_char(make_date(2000, p.month, 1), 'Mon')                              as month_name,
    p.n_market_days,
    round(p.median_price::numeric, 0)                                        as median_price,
    round((percentile_cont(0.5) within group (order by i.idx))::numeric, 3)  as price_index,
    count(i.idx)                                                             as n_years,
    c.n_labelled_days,
    c.n_crash_days,
    round(c.n_crash_days::numeric / nullif(c.n_labelled_days, 0), 4)         as crash_rate
from prices p
join index_by_year i using (commodity, state, month)
left join crashes c using (commodity, state, month)
join {{ ref('dim_commodity') }} c2 on c2.commodity = p.commodity
group by p.commodity, c2.category, p.state, p.month, p.n_market_days, p.median_price,
         c.n_labelled_days, c.n_crash_days
