-- Grain: one row per date x market x commodity, valid rows only (spec 7.5). No gap filling.

select
    to_char(d.arrival_date, 'YYYYMMDD')::integer                      as date_key,
    md5(d.state || '|' || d.district || '|' || d.market)              as market_key,
    c.commodity_key,
    d.modal_price,
    d.min_price,
    d.max_price,
    d.n_varieties,
    d.n_rows,
    d.source,
    d.period
from {{ ref('int_daily_prices') }} d
join {{ ref('dim_commodity') }} c on c.commodity = d.commodity
