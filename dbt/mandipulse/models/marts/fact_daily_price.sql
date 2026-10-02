-- Grain: one row per date x market x commodity with at least one valid row (spec 7.5).
-- No gap filling. modal_price excludes suspect-low rows (NULL when the day is entirely
-- suspect, see is_suspect_low); modal_price_incl_suspect uses every valid row.

select
    to_char(d.arrival_date, 'YYYYMMDD')::integer                      as date_key,
    md5(d.state || '|' || d.district || '|' || d.market)              as market_key,
    c.commodity_key,
    d.modal_price,
    d.min_price,
    d.max_price,
    d.modal_price_incl_suspect,
    d.min_price_incl_suspect,
    d.max_price_incl_suspect,
    d.n_varieties,
    d.n_rows,
    d.n_suspect_rows,
    d.is_suspect_low,
    d.source,
    d.period
from {{ ref('int_daily_prices') }} d
join {{ ref('dim_commodity') }} c on c.commodity = d.commodity
