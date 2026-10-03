-- Sanity: 5 pseudo-random mid-scenario opportunities (fixed hash order, reproducible) with the
-- RAW rows behind both markets' prices that day, for checking by hand:
--   daily price = median of the raw modal prices (valid rows; check flags on each raw row)
--   transport   = road_km_est x 1.5 + 50   (mid scenario)
--   gain        = price_dest - transport - price_home
with pick as (
    select o.*, row_number() over (order by md5(o.pair_key || o.date::text || o.commodity)) as pick_no
    from marts.mart_net_price_opportunities o
    where o.scenario = 'mid'
    order by md5(o.pair_key || o.date::text || o.commodity)
    limit 5
),
sides as (
    select pick_no, 'home' as side, home_market_key as market_key, date, commodity, price_home as daily_price,
           road_km_est, transport_cost, gain
    from pick
    union all
    select pick_no, 'dest', dest_market_key, date, commodity, price_dest, road_km_est, transport_cost, gain
    from pick
)
select
    s.pick_no, s.side, m.state, m.district, m.market, s.commodity, s.date,
    s.daily_price, s.road_km_est, s.transport_cost, s.gain,
    r.raw_id, r.market as raw_market_name, r.variety, r.grade,
    r.min_price as raw_min, r.max_price as raw_max, r.modal_price as raw_modal,
    f.is_valid, f.flag_persistent_low
from sides s
join marts.dim_market m on m.market_key = s.market_key
join intermediate.int_price_flags f
  on f.state = m.state and f.district = m.district and f.market = m.market
 and f.commodity = s.commodity and f.arrival_date = s.date
join raw.mandi_prices r on r.raw_id = f.raw_id
order by s.pick_no, s.side desc, r.raw_id;
