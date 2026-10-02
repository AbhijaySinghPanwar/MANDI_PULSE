-- From late Nov 2025 market names gain an ' APMC' suffix (e.g. 'Lasalgaon' -> 'Lasalgaon APMC').
-- Per state: how many markets were renamed this way, the last date an old name was seen,
-- and the first date a new '... APMC' name was seen.
with names as (
    select state, district, market, min(arrival_date) as first_seen, max(arrival_date) as last_seen
    from scope_prices
    group by all
),
pairs as (
    select o.state, o.last_seen as old_last_seen, n.first_seen as new_first_seen
    from names o
    join names n
      on n.state = o.state and n.district = o.district and n.market = o.market || ' APMC'
)
select state,
       count(*)            as n_renamed_markets,
       max(old_last_seen)  as latest_old_name_seen,
       min(new_first_seen) as earliest_new_name_seen
from pairs
group by state
order by state;
