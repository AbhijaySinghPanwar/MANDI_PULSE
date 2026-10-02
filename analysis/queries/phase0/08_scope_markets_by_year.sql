-- Distinct markets reporting per commodity x state x year.
-- Raw market names, so 2025-2026 double-count markets renamed '<name> APMC' (see 15).
select commodity, state, year(arrival_date) as year,
       count(distinct district || '|' || market) as n_markets
from scope_prices
group by all
order by commodity, state, year;
