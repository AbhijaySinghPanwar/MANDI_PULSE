-- Every raw (state, district, market) must be mapped by reference.market_aliases, and the alias
-- district must agree with the district after corrections.
select raw_id, state, district, alias_district, market_raw, market
from {{ ref('stg_mandi_prices') }}
where market is null or alias_district is distinct from district
