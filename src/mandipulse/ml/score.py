"""Score the latest available dates into ml.price_forecast, ml.crash_risk, ml.market_cluster.

"Latest available" = each series' last anchor in the main period (data end 2025-10-31), kept if
it is within 14 days of the end. Re-running replaces the rows of the same model_version.
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import text

from mandipulse.db import get_engine
from mandipulse.ml.evaluate import REPORT_ML_DIR, latest_run
from mandipulse.ml.features import as_model_frame
from mandipulse.ml.validate_forecast import calibrated_band, load_calibration
from mandipulse.queries import run_sql

SCHEMA_SQL = Path(__file__).with_name("schema.sql")
RECENT_DAYS = 14


def init_schema() -> None:
    with get_engine().begin() as conn:
        conn.exec_driver_sql(SCHEMA_SQL.read_text(encoding="utf-8"))


def _replace(table: str, df: pd.DataFrame, version: str) -> int:
    with get_engine().begin() as conn:
        conn.execute(text(f"delete from ml.{table} where model_version = :v"), {"v": version})
        df.to_sql(
            table,
            conn,
            schema="ml",
            if_exists="append",
            index=False,
            method="multi",
            chunksize=5000,
        )
    return len(df)


def _latest_anchors(f: pd.DataFrame, reported_only: bool) -> pd.DataFrame:
    if reported_only:
        f = f[f["reported"]]
    last = f.loc[f.groupby("series_id")["date"].idxmax()]
    return last[last["date"] >= f["date"].max() - pd.Timedelta(days=RECENT_DAYS)]


def score_all() -> dict:
    from mandipulse.ml.train_forecast import build_frame

    init_schema()
    f = build_frame()
    counts = {}

    run = latest_run("price_forecast")
    models = joblib.load(run / "model.joblib")
    features = json.loads((run / "feature_list.json").read_text(encoding="utf-8"))
    version = f"price_forecast_{run.name}"
    a = _latest_anchors(f, reported_only=False)
    x = as_model_frame(a, features)
    q = np.sort(
        np.column_stack(
            [np.exp(a["lp_t"].astype(float) + models[k].predict(x)) for k in ("p10", "p50", "p90")]
        ),
        axis=1,
    )
    # calibrated band (CQR widening from the pre-test validation window, per commodity)
    widen = a["commodity"].map(load_calibration()).fillna(0.0).to_numpy()
    q[:, 0], q[:, 2] = calibrated_band(q[:, 0], q[:, 1], q[:, 2], widen)
    out = pd.DataFrame(
        {
            "date": a["date"].dt.date,
            "market_key": a["market_key"],
            "commodity_key": a["commodity_key"].astype(int),
            "horizon_date": (a["date"] + pd.Timedelta(days=7)).dt.date,
            "p10": q[:, 0].round(2),
            "p50": q[:, 1].round(2),
            "p90": q[:, 2].round(2),
            "model_version": version,
        }
    )
    counts["price_forecast"] = _replace("price_forecast", out, version)

    # backtest (test months) for the app's forecast chart
    wf = pd.read_parquet(run / "walk_forward_predictions.parquet")
    keys = run_sql("select commodity, commodity_key from marts.dim_commodity")
    wf = wf.merge(keys, on="commodity")
    lo, hi = calibrated_band(
        wf["model_p10"],
        wf["model_p50"],
        wf["model_p90"],
        wf["commodity"].map(load_calibration()).fillna(0.0),
    )
    bt = pd.DataFrame(
        {
            "date": pd.to_datetime(wf["date"]).dt.date,
            "target_date": pd.to_datetime(wf["target_date"]).dt.date,
            "market_key": wf["market_key"],
            "commodity_key": wf["commodity_key"].astype(int),
            "actual_price": wf["target_price"].astype(float).round(2),
            "p10": lo.round(2),
            "p50": wf["model_p50"].round(2),
            "p90": hi.round(2),
            "baseline_last_value": wf["baseline_last_value"].astype(float).round(2),
            "model_version": version,
        }
    )
    counts["price_forecast_backtest"] = _replace("price_forecast_backtest", bt, version)

    run = latest_run("crash_risk")
    bundle = joblib.load(run / "model.joblib")
    features = json.loads((run / "feature_list.json").read_text(encoding="utf-8"))
    version = f"crash_risk_{run.name}"
    c = _latest_anchors(f, reported_only=True).copy()
    keys = pd.MultiIndex.from_arrays([c["commodity"], c["date"].dt.month])
    c["hist_crash_rate"] = (
        bundle["seasonal_table"].reindex(keys).fillna(bundle["base_rate"]).to_numpy()
    )
    prob = bundle["model"].predict_proba(as_model_frame(c, features))[:, 1]
    out = pd.DataFrame(
        {
            "date": c["date"].dt.date,
            "market_key": c["market_key"],
            "commodity_key": c["commodity_key"].astype(int),
            "prob": prob.round(5),
            "alert_flag": prob >= bundle["threshold"],
            "threshold": bundle["threshold"],
            "model_version": version,
        }
    )
    counts["crash_risk"] = _replace("crash_risk", out, version)

    run = latest_run("market_cluster")
    version = f"market_cluster_{run.name}"
    cl = pd.read_csv(REPORT_ML_DIR / "market_clusters.csv")
    cols = [
        "market_key",
        "commodity_key",
        "cluster_id",
        "cluster_name",
        "cv",
        "price_index",
        "report_freq",
        "seasonal_amplitude",
        "crash_rate",
        "n_markets_within_50km",
        "is_suspect_series",
    ]
    out = cl[cols].assign(model_version=version)
    counts["market_cluster"] = _replace("market_cluster", out, version)
    return counts
