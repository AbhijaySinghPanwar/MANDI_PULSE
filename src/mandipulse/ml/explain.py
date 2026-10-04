"""SHAP explanations for Model A and Model B (spec 9.4).

Uses LightGBM's exact TreeSHAP (`pred_contrib=True`, same values as shap.TreeExplainer) on a
sample of 50,000 recent rows. Saves a summary (beeswarm) plot per model to reports/figures/ and the
mean |SHAP| ranking with the direction of each effect to reports/ml/shap_<model>.json.
"""

import json

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

from mandipulse import viz
from mandipulse.ml.evaluate import REPORT_ML_DIR, latest_run
from mandipulse.ml.features import CATEGORICAL, as_model_frame

SAMPLE = 50_000
TOP = 12


def shap_values(model, df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    booster = model.booster_ if hasattr(model, "booster_") else model
    contrib = booster.predict(as_model_frame(df, features), pred_contrib=True)
    return pd.DataFrame(np.asarray(contrib)[:, : len(features)], columns=features, index=df.index)


def summarise(sv: pd.DataFrame, x: pd.DataFrame) -> list[dict]:
    rows = []
    for f in sv.columns:
        direction = None
        if f not in CATEGORICAL and x[f].notna().sum() > 10:
            ranks = x[f].rank()
            direction = round(float(np.corrcoef(ranks.fillna(ranks.median()), sv[f])[0, 1]), 3)
        rows.append(
            {
                "feature": f,
                "mean_abs_shap": round(float(sv[f].abs().mean()), 5),
                "corr_value_vs_shap": direction,
            }
        )
    return sorted(rows, key=lambda r: -r["mean_abs_shap"])


def beeswarm(
    sv: pd.DataFrame,
    x: pd.DataFrame,
    ranking: list[dict],
    title: str,
    subtitle: str,
    xlabel: str,
    name: str,
) -> None:
    top = [r["feature"] for r in ranking[:TOP]]
    cmap = LinearSegmentedColormap.from_list("seq", viz.SEQUENTIAL)
    rng = np.random.default_rng(0)
    viz.style()
    fig, ax = plt.subplots(figsize=(9, 6.4))
    viz.header(fig, title, subtitle)
    for i, f in enumerate(reversed(top)):
        vals = sv[f].to_numpy()
        if f in CATEGORICAL or x[f].notna().sum() == 0:
            colors = viz.MUTED
        else:
            pct = x[f].rank(pct=True).fillna(0.5).to_numpy()
            colors = cmap(pct)
        ax.scatter(
            vals,
            i + rng.uniform(-0.28, 0.28, len(vals)),
            s=3,
            c=colors,
            alpha=0.5,
            linewidths=0,
            rasterized=True,
        )
    ax.axvline(0, color=viz.AXIS, linewidth=0.8)
    ax.set_yticks(range(len(top)), list(reversed(top)))
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.set_xlabel(xlabel)
    sm = plt.cm.ScalarMappable(cmap=cmap)
    cb = fig.colorbar(sm, ax=ax, shrink=0.6, pad=0.02)
    cb.set_ticks([0, 1], labels=["low", "high"])
    cb.set_label("feature value (grey = categorical)")
    viz.save(
        fig,
        name,
        note="Each dot is one sampled row; position = SHAP contribution, colour = feature value.",
    )


def explain_model(
    name: str, frame: pd.DataFrame, title: str, subtitle: str, xlabel: str
) -> list[dict]:
    run = latest_run(name)
    obj = joblib.load(run / "model.joblib")
    features = json.loads((run / "feature_list.json").read_text(encoding="utf-8"))
    if isinstance(obj, dict) and "p50" in obj:  # forecast: dict of quantile models
        model = obj["p50"]
    elif isinstance(obj, dict):  # crash: bundle with model + threshold + seasonal table
        model = obj["model"]
    else:
        model = obj
    if "hist_crash_rate" in features and "hist_crash_rate" not in frame:
        keys = pd.MultiIndex.from_arrays([frame["commodity"], frame["date"].dt.month])
        frame = frame.assign(
            hist_crash_rate=obj["seasonal_table"].reindex(keys).fillna(obj["base_rate"]).to_numpy()
        )
    sample = frame.sample(min(SAMPLE, len(frame)), random_state=42)
    sv = shap_values(model, sample, features)
    ranking = summarise(sv, sample[features])
    beeswarm(sv, sample[features], ranking, title, subtitle, xlabel, f"shap_{name}")
    REPORT_ML_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_ML_DIR / f"shap_{name}.json").write_text(
        json.dumps(ranking, indent=2), encoding="utf-8"
    )
    return ranking


def explain_all() -> dict:
    from mandipulse.ml.train_crash import build_crash_frame
    from mandipulse.ml.train_forecast import build_frame

    f = build_frame()
    recent = f[(f["date"] >= "2024-01-01") & f["target_lp"].notna()]
    out = {
        "price_forecast": explain_model(
            "price_forecast",
            recent,
            "What drives the 7-day price forecast (Model A)",
            "SHAP values on 50,000 forecasts from 2024-2025, top 12 features",
            "contribution to predicted 7-day log price change",
        )
    }
    c = build_crash_frame()
    out["crash_risk"] = explain_model(
        "crash_risk",
        c[c["date"] >= "2023-01-01"],
        "What drives the crash warning (Model B)",
        "SHAP values on 50,000 labelled report days from 2023-2025, top 12 features",
        "contribution to crash log-odds",
    )
    return out
