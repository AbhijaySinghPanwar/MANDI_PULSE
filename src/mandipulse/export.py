"""Exports for Power BI and the app's parquet backend (spec 10.2).

    python -m mandipulse export

exports/powerbi/<table>.parquet + .csv   star schema, analysis marts, ml outputs
    The three pair-level marts (6-7 M rows each) are exported as MONTHLY aggregates plus the
    LATEST 90 DAYS of detail, so Power BI files stay manageable.
exports/app/<dataset>.parquet             the app datasets (same SQL as mandipulse.serving)
exports/manifest.csv                      every file with row count and size
"""

from pathlib import Path

import pandas as pd

from mandipulse.queries import run_sql
from mandipulse.serving import APP_EXPORT_DIR, DATASETS, EXPORT_DIR

PBI_DIR = EXPORT_DIR / "powerbi"
LATEST = "(select max(date) from marts.int_analysis_prices)"

POWERBI: dict[str, str] = {
    "dim_date": "select * from marts.dim_date order by date_key",
    "dim_commodity": "select * from marts.dim_commodity order by commodity_key",
    "dim_market": "select * from marts.dim_market order by market_key",
    "fact_daily_price": "select * from marts.fact_daily_price order by date_key, market_key, commodity_key",
    "mart_seasonality": "select * from marts.mart_seasonality order by commodity, state, month",
    "mart_volatility": "select * from marts.mart_volatility order by commodity, market_key, year",
    # district centre = mean position of its geocoded markets (Power BI cannot geocode districts reliably)
    "mart_district_access": """
        select a.*, round(g.latitude::numeric, 5) as latitude, round(g.longitude::numeric, 5) as longitude
        from marts.mart_district_access a
        left join (
            select state, district, avg(latitude) as latitude, avg(longitude) as longitude
            from marts.dim_market where latitude is not null group by 1, 2
        ) g using (state, district)
        order by a.state, a.district, a.commodity
    """,
    "mart_price_spread_daily": "select * from marts.mart_price_spread_daily order by date, commodity, state",
    # --- pair-level marts: monthly aggregates + latest 90 days of detail ------------------
    "mart_price_spread_monthly": """
        select date_trunc('month', date)::date as month, commodity_key, commodity,
               market_key_a, market_key_b, pair_key, road_km_est, pair_precision,
               count(*) as n_days,
               round(avg(abs_gap), 2) as avg_abs_gap,
               round((percentile_cont(0.5) within group (order by pct_gap))::numeric, 4) as median_pct_gap
        from marts.mart_price_spread
        group by 1, 2, 3, 4, 5, 6, 7, 8
        order by 1, pair_key, commodity_key
    """,
    "mart_price_spread_latest90": f"""
        select * from marts.mart_price_spread where date > {LATEST} - 90
        order by date, pair_key, commodity_key
    """,
    "mart_net_price_opportunities_monthly": """
        select date_trunc('month', date)::date as month, scenario, commodity_key, commodity,
               home_market_key, dest_market_key, road_km_est, pair_precision,
               count(*) as n_opportunity_days,
               round(avg(gain), 2) as avg_gain, round(max(gain), 2) as max_gain
        from marts.mart_net_price_opportunities
        group by 1, 2, 3, 4, 5, 6, 7, 8
        order by 1, scenario, home_market_key, dest_market_key, commodity_key
    """,
    "mart_net_price_opportunities_latest90": f"""
        select * from marts.mart_net_price_opportunities where date > {LATEST} - 90
        order by date, scenario, home_market_key, dest_market_key, commodity_key
    """,
    "mart_opportunity_market_day_monthly": """
        select date_trunc('month', date)::date as month, scenario, commodity_key, commodity,
               home_market_key,
               count(*) as n_market_days,
               count(*) filter (where has_opportunity) as n_opportunity_days,
               round(avg(has_opportunity::int), 4) as opportunity_rate,
               round(avg(best_opportunity_gain), 2) as avg_best_gain_when_opportunity,
               round(avg(n_neighbors_reporting), 2) as avg_neighbors_reporting
        from marts.mart_opportunity_market_day
        group by 1, 2, 3, 4, 5
        order by 1, scenario, home_market_key, commodity_key
    """,
    "mart_opportunity_market_day_latest90": f"""
        select * from marts.mart_opportunity_market_day where date > {LATEST} - 90
        order by date, scenario, home_market_key, commodity_key
    """,
    # --- ml outputs -------------------------------------------------------------------------
    "ml_price_forecast": "select * from ml.price_forecast order by date, market_key, commodity_key",
    "ml_price_forecast_backtest": "select * from ml.price_forecast_backtest order by target_date, market_key, commodity_key",
    "ml_crash_risk": "select * from ml.crash_risk order by date, market_key, commodity_key",
    "ml_market_cluster": "select * from ml.market_cluster order by market_key, commodity_key",
    # latest status per series: ratio to 30-day median ("falling now") + model risk (same SQL as the app)
    "ml_crash_status_latest": DATASETS["crash_status"],
}


def _size_mb(path: Path) -> float:
    return round(path.stat().st_size / 1e6, 2)


def export_all(progress=print) -> pd.DataFrame:
    PBI_DIR.mkdir(parents=True, exist_ok=True)
    APP_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, sql in POWERBI.items():
        df = run_sql(sql)
        pq, csv = PBI_DIR / f"{name}.parquet", PBI_DIR / f"{name}.csv"
        df.to_parquet(pq, index=False)
        df.to_csv(csv, index=False)
        rows.append(
            {
                "file": f"powerbi/{name}",
                "rows": len(df),
                "parquet_mb": _size_mb(pq),
                "csv_mb": _size_mb(csv),
            }
        )
        progress(f"  powerbi/{name}: {len(df):,} rows")
    for name, sql in DATASETS.items():
        df = run_sql(sql)
        pq = APP_EXPORT_DIR / f"{name}.parquet"
        df.to_parquet(pq, index=False)
        rows.append(
            {"file": f"app/{name}", "rows": len(df), "parquet_mb": _size_mb(pq), "csv_mb": None}
        )
        progress(f"  app/{name}: {len(df):,} rows")
    manifest = pd.DataFrame(rows)
    manifest.to_csv(EXPORT_DIR / "manifest.csv", index=False)
    return manifest
