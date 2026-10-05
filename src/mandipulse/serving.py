"""Read-only data access for the Streamlit app (spec 10.1).

Each dataset is ONE saved SQL query over the marts / ml schemas. Two backends, chosen with the
environment variable DATA_BACKEND:
  postgres (default)  run the SQL against DATABASE_URL
  parquet             read exports/app/<dataset>.parquet, written by `python -m mandipulse export`
                      from the very same SQL, so both backends return identical tables
Pages filter these small tables in pandas; they never touch raw or staging tables.
Saved result files (reports/ml/*.json, reports/tables/...) are read directly from the repo.
"""

import json
import os
from pathlib import Path

import pandas as pd

from mandipulse.config import PROJECT_ROOT

# MANDIPULSE_EXPORT_DIR overrides exports/ (e.g. a throwaway folder for a CI-style run)
EXPORT_DIR = Path(os.environ.get("MANDIPULSE_EXPORT_DIR") or PROJECT_ROOT / "exports")
APP_EXPORT_DIR = EXPORT_DIR / "app"
LATEST = "(select max(date) from marts.int_analysis_prices)"

DATASETS: dict[str, str] = {
    "meta": """
        select min(date) as data_from, max(date) as data_as_of, count(*) as n_market_days
        from marts.int_analysis_prices
    """,
    "markets": """
        select market_key, market, district, state, latitude, longitude, geo_precision, town_key,
               n_report_days, last_report_date
        from marts.dim_market
        where has_valid_data
        order by state, district, market
    """,
    "latest_prices": f"""
        with p as (
            select * from marts.int_analysis_prices where date > {LATEST} - 30
        )
        select market_key, commodity,
               max(date)                                          as last_report_date,
               (array_agg(modal_price order by date desc))[1]     as last_price,
               count(*)                                           as report_days_last_30
        from p
        group by market_key, commodity
        order by market_key, commodity
    """,
    "suspect_series": """
        select distinct m.market_key, f.commodity
        from intermediate.int_price_flags f
        join marts.dim_market m on m.state = f.state and m.district = f.district and m.market = f.market
        where f.flag_persistent_low
        order by m.market_key, f.commodity
    """,
    "price_history": f"""
        select market_key, commodity, date, modal_price
        from marts.int_analysis_prices
        where date > {LATEST} - 200
        order by market_key, commodity, date
    """,
    "forecast_latest": """
        select f.market_key, c.commodity, f.date, f.horizon_date, f.p10, f.p50, f.p90
        from ml.price_forecast f
        join marts.dim_commodity c using (commodity_key)
        where f.model_version = (select max(model_version) from ml.price_forecast)
        order by f.market_key, c.commodity
    """,
    "forecast_backtest": """
        select b.market_key, c.commodity, b.date, b.target_date, b.actual_price, b.p10, b.p50,
               b.p90, b.baseline_last_value
        from ml.price_forecast_backtest b
        join marts.dim_commodity c using (commodity_key)
        where b.model_version = (select max(model_version) from ml.price_forecast_backtest)
        order by b.market_key, c.commodity, b.target_date
    """,
    "crash_status": f"""
        with last as (
            select distinct on (market_key, commodity_key)
                   market_key, commodity_key, commodity, date, modal_price, lookback_median
            from marts.int_crash_labels
            where date >= {LATEST} - 14
            order by market_key, commodity_key, date desc
        )
        select l.market_key, l.commodity, l.date, l.modal_price,
               round(l.lookback_median::numeric, 2)                   as median_30d,
               round((l.modal_price / l.lookback_median)::numeric, 4) as ratio_to_median,
               r.prob, r.alert_flag, r.threshold,
               exists (
                   select 1
                   from intermediate.int_price_flags f
                   join marts.dim_market m
                     on m.state = f.state and m.district = f.district and m.market = f.market
                   where f.flag_persistent_low and m.market_key = l.market_key
                     and f.commodity = l.commodity
               )                                                      as is_suspect_series
        from last l
        left join ml.crash_risk r
          on r.market_key = l.market_key and r.commodity_key = l.commodity_key and r.date = l.date
         and r.model_version = (select max(model_version) from ml.crash_risk)
        order by l.market_key, l.commodity
    """,
    "district_access": """
        select state, district, commodity, n_markets_within_50km, avg_price_index,
               opportunity_rate, is_price_trapped, n_price_days
        from marts.mart_district_access
        order by state, district, commodity
    """,
    "clusters": """
        select k.market_key, m.market, m.district, m.state, c.commodity, k.cluster_id,
               k.cluster_name, k.cv, k.price_index, k.report_freq, k.seasonal_amplitude,
               k.crash_rate, k.n_markets_within_50km, k.is_suspect_series
        from ml.market_cluster k
        join marts.dim_market m using (market_key)
        join marts.dim_commodity c using (commodity_key)
        where k.model_version = (select max(model_version) from ml.market_cluster)
        order by m.state, m.district, m.market, c.commodity
    """,
}


def backend() -> str:
    b = os.environ.get("DATA_BACKEND", "postgres").strip().lower()
    if b not in {"postgres", "parquet"}:
        raise ValueError(f"DATA_BACKEND must be 'postgres' or 'parquet', got {b!r}")
    return b


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    """Same dtypes whatever the backend: dates as pandas Timestamps, numbers as float."""
    df = df.copy()
    for col in df.columns:
        if col == "date" or col.endswith("_date") or col in {"data_from", "data_as_of"}:
            df[col] = pd.to_datetime(df[col])
    for col in df.select_dtypes(include=["int64", "int32", "Int64"]).columns:
        df[col] = df[col].astype(float)
    return df.reset_index(drop=True)


def load(name: str, which: str | None = None) -> pd.DataFrame:
    which = which or backend()
    if name not in DATASETS:
        raise KeyError(name)
    if which == "parquet":
        path = APP_EXPORT_DIR / f"{name}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"{path} missing - run `python -m mandipulse export` first")
        return _normalise(pd.read_parquet(path))
    from mandipulse.queries import run_sql

    return _normalise(run_sql(DATASETS[name]))


def read_json(relative: str) -> dict:
    return json.loads((PROJECT_ROOT / relative).read_text(encoding="utf-8"))


def read_csv(relative: str) -> pd.DataFrame:
    return pd.read_csv(PROJECT_ROOT / relative)


def repo_path(relative: str) -> Path:
    return PROJECT_ROOT / relative
