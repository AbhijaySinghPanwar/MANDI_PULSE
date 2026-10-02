-- Headline sizes of the marts.
select 'dim_date' as table_name, count(*) as n_rows, min(date)::text as min_value, max(date)::text as max_value from marts.dim_date
union all select 'dim_commodity', count(*), null, null from marts.dim_commodity
union all select 'dim_market', count(*), null, null from marts.dim_market
union all select 'dim_market: distinct town_key', count(distinct town_key), null, null from marts.dim_market
union all select 'dim_market: markets sharing a town_key', count(*) filter (where n_markets_in_town > 1), null, null from marts.dim_market
union all select 'dim_market: markets with no valid daily price', count(*) filter (where n_report_days = 0), null, null from marts.dim_market
union all select 'fact_daily_price', count(*), min(date_key)::text, max(date_key)::text from marts.fact_daily_price
union all select 'fact_daily_price: period main', count(*) filter (where period = 'main'), null, null from marts.fact_daily_price
union all select 'fact_daily_price: period post_format_change', count(*) filter (where period = 'post_format_change'), null, null from marts.fact_daily_price;
