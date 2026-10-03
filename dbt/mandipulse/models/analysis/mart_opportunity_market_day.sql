-- Q2 rate denominator: one row per home market x commodity x date x scenario, for every
-- market-day where the home market reported AND at least one market within spread_radius_km
-- also reported. has_opportunity = at least one destination is a profitable move that day.
-- *_market_precision columns repeat the logic using only pairs where both markets were
-- geocoded at market level (robustness check, no centroid fallbacks).
{{ config(indexes=[{'columns': ['scenario', 'commodity_key', 'date']}, {'columns': ['home_market_key']}]) }}

select
    home_market_key,
    date_key,
    date,
    commodity_key,
    commodity,
    scenario,
    count(*)                                                        as n_neighbors_reporting,
    count(*) filter (where is_opportunity)                          as n_opportunities,
    max(gain)                                                       as best_gain,
    bool_or(is_opportunity)                                         as has_opportunity,
    max(gain) filter (where is_opportunity)                         as best_opportunity_gain,
    count(*) filter (where pair_precision = 'both_market')          as n_neighbors_market_precision,
    coalesce(bool_or(is_opportunity) filter (where pair_precision = 'both_market'), false)
                                                                    as has_opportunity_market_precision
from {{ ref('int_directed_comparisons') }}
group by home_market_key, date_key, date, commodity_key, commodity, scenario
