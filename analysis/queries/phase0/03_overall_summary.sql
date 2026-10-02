-- Whole-archive size and date range.
select
    count(*)                                                  as n_rows,
    min(arrival_date)                                         as first_date,
    max(arrival_date)                                         as last_date,
    count(*) filter (where arrival_date is null)              as n_unparseable_dates,
    count(distinct state)                                     as n_states,
    count(distinct commodity)                                 as n_commodities,
    count(distinct state || '|' || district)                  as n_districts,
    count(distinct state || '|' || district || '|' || market) as n_markets
from prices;
