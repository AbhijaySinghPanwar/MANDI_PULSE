-- ML output tables (spec 9.5), written by `python -m mandipulse ml score`.
-- `python -m mandipulse ml init-schema` creates them empty (CI runs dbt tests on them).

create schema if not exists ml;

create table if not exists ml.price_forecast (
    date            date    not null,   -- forecast made with data up to this day
    market_key      text    not null,
    commodity_key   integer not null,
    horizon_date    date    not null,   -- date + 7
    p10             numeric not null,   -- Rs per quintal
    p50             numeric not null,
    p90             numeric not null,
    model_version   text    not null,
    primary key (date, market_key, commodity_key, horizon_date, model_version)
);

create table if not exists ml.crash_risk (
    date            date    not null,
    market_key      text    not null,
    commodity_key   integer not null,
    prob            double precision not null,  -- probability of a crash in the next 14 days
    alert_flag      boolean not null,
    threshold       double precision not null,
    model_version   text    not null,
    primary key (date, market_key, commodity_key, model_version)
);

create table if not exists ml.market_cluster (
    market_key            text    not null,
    commodity_key         integer not null,
    cluster_id            integer not null,
    cluster_name          text    not null,
    cv                    double precision,
    price_index           double precision,
    report_freq           double precision,
    seasonal_amplitude    double precision,
    crash_rate            double precision,
    n_markets_within_50km integer,
    is_suspect_series     boolean,
    model_version         text    not null,
    primary key (market_key, commodity_key, model_version)
);

-- Model A walk-forward backtest (test months May-Oct 2025): what the model said 7 days ahead,
-- with the calibrated p10-p90 band and the last-value baseline, next to the real price.
create table if not exists ml.price_forecast_backtest (
    date                 date    not null,   -- forecast made with data up to this day
    target_date          date    not null,   -- date + 7 (a real report exists on this day)
    market_key           text    not null,
    commodity_key        integer not null,
    actual_price         numeric not null,
    p10                  numeric not null,   -- calibrated band
    p50                  numeric not null,
    p90                  numeric not null,
    baseline_last_value  numeric not null,
    model_version        text    not null,
    primary key (target_date, market_key, commodity_key, model_version)
);
