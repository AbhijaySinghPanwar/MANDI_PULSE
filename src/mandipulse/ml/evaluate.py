"""Metrics and artifact helpers shared by the ML models."""

import json
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import precision_recall_curve

from mandipulse.config import PROJECT_ROOT, get_settings

MODELS_DIR = PROJECT_ROOT / "models"  # gitignored (large binaries)
REPORT_ML_DIR = PROJECT_ROOT / "reports" / "ml"  # committed copies of metrics / tables


# ----------------------------------------------------------------------------- regression
def regression_metrics(actual: np.ndarray, pred: np.ndarray) -> dict:
    """MAE, MAPE and sMAPE (Rs/qtl and %)."""
    actual, pred = np.asarray(actual, float), np.asarray(pred, float)
    err = pred - actual
    return {
        "n": int(len(actual)),
        "mae_rs_qtl": round(float(np.mean(np.abs(err))), 1),
        "mape_pct": round(float(100 * np.mean(np.abs(err) / actual)), 2),
        "smape_pct": round(
            float(100 * np.mean(2 * np.abs(err) / (np.abs(actual) + np.abs(pred)))), 2
        ),
    }


def coverage(actual, p10, p90) -> float:
    """Share (%) of actual values inside [p10, p90]."""
    actual = np.asarray(actual, float)
    return round(float(100 * np.mean((actual >= p10) & (actual <= p90))), 1)


def grouped_regression(df: pd.DataFrame, pred_cols: list[str], by: list[str]) -> list[dict]:
    """Metrics for each prediction column, overall and per group (rows = model x group)."""
    out = []
    groups = (
        [("all", df)]
        + [(k if isinstance(k, str) else "|".join(map(str, k)), g) for k, g in df.groupby(by)]
        if by
        else [("all", df)]
    )
    for name, g in groups:
        for col in pred_cols:
            out.append(
                {"group": name, "model": col, **regression_metrics(g["target_price"], g[col])}
            )
    return out


# ------------------------------------------------------------------------- classification
def pick_threshold(y: np.ndarray, score: np.ndarray, target_precision: float) -> tuple[float, bool]:
    """Lowest threshold whose precision >= target (max recall at that precision). If no
    threshold reaches it, the threshold with the best F1 (flag returned False)."""
    prec, rec, thr = precision_recall_curve(y, score)
    prec, rec = prec[:-1], rec[:-1]
    ok = np.where(prec >= target_precision)[0]
    if len(ok):
        return float(thr[ok[0]]), True
    f1 = 2 * prec * rec / np.clip(prec + rec, 1e-9, None)
    return float(thr[int(np.argmax(f1))]), False


# ------------------------------------------------------------------------------ artifacts
def save_artifacts(
    name: str, model, metrics: dict, features: list[str], extra: dict | None = None
) -> Path:
    """models/<name>/<YYYYMMDD>/: model.joblib, metrics.json, feature_list.json,
    config_snapshot.yaml
    plus a committed copy of the metrics in reports/ml/<name>_metrics.json."""
    run_dir = MODELS_DIR / name / date.today().strftime("%Y%m%d")
    run_dir.mkdir(parents=True, exist_ok=True)
    if model is not None:
        joblib.dump(model, run_dir / "model.joblib")
    payload = {"model": name, "version": f"{name}_{run_dir.name}", **metrics}
    (run_dir / "metrics.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    (run_dir / "feature_list.json").write_text(json.dumps(features, indent=2), encoding="utf-8")
    snapshot = {"settings": get_settings(), **(extra or {})}
    (run_dir / "config_snapshot.yaml").write_text(
        yaml.safe_dump(snapshot, sort_keys=False), encoding="utf-8"
    )
    REPORT_ML_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_ML_DIR / f"{name}_metrics.json").write_text(
        json.dumps(payload, indent=2, default=str), encoding="utf-8"
    )
    return run_dir


def latest_run(name: str) -> Path:
    """Folder of the newest trained run of a model (models/<name>/<timestamp>/)."""
    runs = sorted((MODELS_DIR / name).glob("*/model.joblib"))
    if not runs:
        raise FileNotFoundError(
            f"No trained model for {name}; run `python -m mandipulse ml train-all`."
        )
    return runs[-1].parent
