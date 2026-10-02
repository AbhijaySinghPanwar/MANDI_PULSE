-- Distinct report dates per raw market name (any commodity); used by the alias merge rule.
select distinct state, district, market, arrival_date
from raw.mandi_prices;
