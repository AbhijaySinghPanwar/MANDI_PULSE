-- Raw layer: rows exactly as received, plus lineage columns. {schema} is filled in by load.py.

create schema if not exists {schema};

create table if not exists {schema}.mandi_prices (
    raw_id          bigint generated always as identity primary key,
    state           text not null,
    district        text not null,
    market          text not null,
    commodity       text not null,
    variety         text,
    grade           text,
    arrival_date    date not null,
    min_price       numeric,
    max_price       numeric,
    modal_price     numeric not null,
    commodity_code  integer,
    source          text not null,          -- kaggle_archive | ceda | datagov_daily
    source_file     text,                   -- e.g. 2024.parquet
    period          text not null,          -- main | post_format_change
    ingested_at     timestamptz not null,
    run_id          uuid not null
);

create index if not exists mandi_prices_source_idx on {schema}.mandi_prices (source);
create index if not exists mandi_prices_date_idx on {schema}.mandi_prices (arrival_date);
create index if not exists mandi_prices_scope_idx on {schema}.mandi_prices (state, commodity, arrival_date);

create table if not exists {schema}.ingest_log (
    run_id          uuid primary key,
    source          text not null,
    started_at      timestamptz not null,
    finished_at     timestamptz,
    rows_fetched    bigint,                 -- rows matching the scope filter
    rows_rejected   bigint,                 -- rows failing basic validation (not loaded)
    rows_loaded     bigint,
    rows_replaced   bigint,                 -- rows of the same source deleted by this run
    status          text not null,          -- running | success | failed
    error           text
);
