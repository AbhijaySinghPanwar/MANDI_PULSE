select
    commodity_key,
    commodity,
    category
from {{ ref('commodity_category') }}
