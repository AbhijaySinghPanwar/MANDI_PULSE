-- State-level date gaps: per commodity x state x year, the number of calendar days with
-- at least one report anywhere in the state, the longest run of days with no report
-- (gap measured from the previous report day, which may fall in the prior year),
-- and the number of gaps longer than 7 days.
with days as (
    select distinct commodity, state, arrival_date from scope_prices
),
lagged as (
    select *,
           arrival_date - lag(arrival_date) over (
               partition by commodity, state order by arrival_date) as gap_days
    from days
)
select
    commodity, state, year(arrival_date) as year,
    count(*)                             as days_with_data,
    max(gap_days) - 1                    as longest_gap_days,
    count(*) filter (where gap_days > 8) as n_gaps_over_7d
from lagged
group by all
order by commodity, state, year;
