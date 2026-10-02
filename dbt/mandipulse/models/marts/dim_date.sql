-- Calendar covering every date in the fact table (no gaps, so time intelligence works).

with bounds as (
    select min(arrival_date) as d0, max(arrival_date) as d1 from {{ ref('int_daily_prices') }}
),

days as (
    select generate_series(d0, d1, interval '1 day')::date as date from bounds
)

select
    to_char(date, 'YYYYMMDD')::integer           as date_key,
    date,
    extract(isodow from date)::integer           as day_of_week,      -- 1 = Monday
    trim(to_char(date, 'Day'))                   as day_name,
    extract(week from date)::integer             as week,             -- ISO week
    extract(month from date)::integer            as month,
    trim(to_char(date, 'Month'))                 as month_name,
    extract(quarter from date)::integer          as quarter,
    extract(year from date)::integer             as year,
    extract(isodow from date) in (6, 7)          as is_weekend,
    case when date <= date '{{ var("main_end") }}' then 'main' else 'post_format_change' end as period
from days
