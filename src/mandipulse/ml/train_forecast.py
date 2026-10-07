"""Model A: 7-day-ahead price forecast (spec 9.1).

* One global LightGBM on the 7-day log change (target = log real price on t+7 - log price at t),
  fitted as quantile models: alpha 0.5 (the point forecast, matches the MAE metric) and
  alpha 0.1 / 0.9 for a p10-p90 band.
* Baselines on exactly the same rows: last value, value 7 days ago, 7-day moving average.
* Walk-forward: one fold per test month (ml.walk_forward_test_months), split by TARGET date:
  train on targets dated before the month, test on targets inside it. Never shuffled.
* Segments: frequent reporters (>= 15 report days in the 30 days up to t) vs sparse.
* Stress test: train on targets before 2023-07-01, test July-August 2023 (tomato spike).
"""

import json

import lightgbm as lgb
import numpy as np
import pandas as pd

from mandipulse.config import get_settings
from mandipulse.ml.data import load_prices
from mandipulse.ml.evaluate import (
    REPORT_ML_DIR,
    coverage,
    grouped_regression,
    regression_metrics,
    save_artifacts,
)
from mandipulse.ml.features import (
    CATEGORICAL,
    FORECAST_FEATURES,
    add_features,
    as_model_frame,
    daily_grid,
)

BASELINES = ["baseline_last_value", "baseline_value_7d_ago", "baseline_ma7"]
STRESS_TRAIN_END = pd.Timestamp("2023-07-01")
STRESS_TEST_END = pd.Timestamp("2023-08-31")
FREQUENT_MIN_DAYS = 15


def lgb_params(seed: int, objective: str = "regression", alpha: float | None = None) -> dict:
    """LightGBM settings shared by every Model A fit."""
    params = dict(
        objective=objective,
        n_estimators=400,
        learning_rate=0.05,
        num_leaves=63,
        min_child_samples=100,
        subsample=0.8,
        subsample_freq=1,
        colsample_bytree=0.8,
        random_state=seed,
        deterministic=True,
        force_row_wise=True,
        verbose=-1,
        n_jobs=-1,
    )
    if alpha is not None:
        params["alpha"] = alpha
    return params


def build_frame() -> pd.DataFrame:
    """Model A frame: daily grid with features and the 7-day-ahead target."""
    cfg = get_settings()["ml"]
    f = add_features(
        daily_grid(load_prices()), cfg["ffill_limit_days"], cfg["forecast_horizon_days"]
    )
    f = f[f["lp_t"].notna()].copy()  # anchors with a (recent) price at t
    f["segment"] = np.where(f["report_freq_30"] >= FREQUENT_MIN_DAYS, "frequent", "sparse")
    last = np.exp(f["lp_t"])
    f["baseline_last_value"] = last
    f["baseline_value_7d_ago"] = np.exp(f["lag_7"]).fillna(last)
    f["baseline_ma7"] = f["price_ma7"].fillna(last)
    floats = f.select_dtypes("float64").columns
    f[floats] = f[floats].astype("float32")
    return f


def eligible(f: pd.DataFrame, before: pd.Timestamp, min_days: int) -> pd.Series:
    """Series with >= min_days real reports before `before` (spec: drop short series)."""
    counts = f[(f["date"] < before)].groupby("series_id")["lp_obs"].count()
    return f["series_id"].isin(counts[counts >= min_days].index)


def fit_models(train: pd.DataFrame, seed: int, quantiles=(0.1, 0.9)) -> dict:
    """Fit the p10 / p50 / p90 quantile models on log-price changes."""
    x = as_model_frame(train, FORECAST_FEATURES)
    y = train["target_lp"] - train["lp_t"]
    # p50 = median (quantile 0.5): MAE is minimised by the median, not the mean (run 1 used L2
    # and only matched the last-value baseline; its metrics are kept in reports/ml/attempts/).
    models = {
        "p50": lgb.LGBMRegressor(**lgb_params(seed, "quantile", 0.5)).fit(
            x, y, categorical_feature=CATEGORICAL
        )
    }
    for q in quantiles:
        name = f"p{int(q * 100)}"
        models[name] = lgb.LGBMRegressor(**lgb_params(seed, "quantile", q)).fit(
            x, y, categorical_feature=CATEGORICAL
        )
    return models


def predict(models: dict, df: pd.DataFrame) -> pd.DataFrame:
    """Price forecasts (Rs/qtl) from fitted models, quantiles kept in order."""
    x = as_model_frame(df, FORECAST_FEATURES)
    out = pd.DataFrame(index=df.index)
    for name, m in models.items():
        out[f"model_{name}"] = np.exp(df["lp_t"].astype(float) + m.predict(x))
    q = np.sort(out[["model_p10", "model_p50", "model_p90"]].to_numpy(), axis=1)  # no crossing
    out["model_p10"], out["model_p50"], out["model_p90"] = q[:, 0], q[:, 1], q[:, 2]
    return out


def run_fold(f, train_mask, test_mask, seed) -> pd.DataFrame:
    """Train on one fold's training rows and predict its test rows."""
    train, test = f[train_mask], f[test_mask]
    models = fit_models(train, seed)
    preds = predict(models, test)
    keep = [
        "date",
        "target_date",
        "market_key",
        "commodity",
        "state",
        "segment",
        "target_price",
        "report_freq_30",
        *BASELINES,
    ]
    return pd.concat([test[keep], preds], axis=1)


def summarise(p: pd.DataFrame) -> dict:
    """Model vs baseline metrics overall, by crop and by segment."""
    cols = ["model_p50", *BASELINES]
    res = {
        "overall": grouped_regression(p, cols, []),
        "by_commodity": grouped_regression(p, cols, ["commodity"]),
        "by_segment": grouped_regression(p, cols, ["segment"]),
        "by_commodity_segment": grouped_regression(p, cols, ["commodity", "segment"]),
        "band_coverage_pct": {
            "all": coverage(p["target_price"], p["model_p10"], p["model_p90"]),
            **{
                k: coverage(g["target_price"], g["model_p10"], g["model_p90"])
                for k, g in p.groupby("segment")
            },
        },
    }
    overall = {r["model"]: r["mae_rs_qtl"] for r in res["overall"]}
    best = min(BASELINES, key=lambda b: overall[b])
    res["best_baseline"] = best
    res["mae_improvement_vs_best_baseline_pct"] = round(
        100 * (overall[best] - overall["model_p50"]) / overall[best], 1
    )
    return res


def train_forecast() -> dict:
    """Model A: walk-forward test months, stress test, saved model and metrics."""
    cfg = get_settings()["ml"]
    seed = cfg["random_seed"]
    f = build_frame()
    has_target = f["target_lp"].notna()
    folds = []
    for month in cfg["walk_forward_test_months"]:
        start = pd.Timestamp(f"{month}-01")
        end = start + pd.offsets.MonthEnd(0)
        ok = eligible(f, start, cfg["min_series_days"])
        train = has_target & ok & (f["target_date"] < start)
        test = has_target & ok & (f["target_date"] >= start) & (f["target_date"] <= end)
        p = run_fold(f, train, test, seed)
        p["fold"] = month
        folds.append(p)
        print(f"  fold {month}: train {int(train.sum()):,} rows, test {int(test.sum()):,}")
    wf = pd.concat(folds, ignore_index=True)

    ok = eligible(f, STRESS_TRAIN_END, cfg["min_series_days"])
    stress = run_fold(
        f,
        has_target & ok & (f["target_date"] < STRESS_TRAIN_END),
        has_target
        & ok
        & (f["target_date"] >= STRESS_TRAIN_END)
        & (f["target_date"] <= STRESS_TEST_END),
        seed,
    )
    print(f"  stress test: {len(stress):,} rows")

    final_train = has_target & eligible(
        f, f["date"].max() + pd.Timedelta(days=1), cfg["min_series_days"]
    )
    final = fit_models(f[final_train], seed)

    metrics = {
        "target": "real modal price on t+7 (Rs/qtl); model trained on log change",
        "walk_forward_test_months": cfg["walk_forward_test_months"],
        "n_train_rows_final": int(final_train.sum()),
        "walk_forward": summarise(wf),
        "walk_forward_by_fold": {
            m: regression_metrics(g["target_price"], g["model_p50"]) for m, g in wf.groupby("fold")
        },
        "stress_test_jul_aug_2023": {
            "train_target_dates_before": str(STRESS_TRAIN_END.date()),
            **summarise(stress),
            "tomato": grouped_regression(
                stress[stress["commodity"] == "Tomato"], ["model_p50", *BASELINES], []
            ),
        },
    }
    run_dir = save_artifacts(
        "price_forecast", final, metrics, FORECAST_FEATURES, {"lgb_params": lgb_params(seed)}
    )
    REPORT_ML_DIR.mkdir(parents=True, exist_ok=True)
    wf.to_parquet(run_dir / "walk_forward_predictions.parquet")
    stress.to_parquet(run_dir / "stress_test_predictions.parquet")
    _stress_chart(stress)
    return metrics


def _stress_chart(stress: pd.DataFrame, prices: pd.DataFrame | None = None) -> None:
    """Actual vs forecast (made 7 days earlier) for the 3 tomato markets with most stress rows."""
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    from mandipulse import viz

    if prices is None:
        prices = load_prices()
    tom = stress[stress["commodity"] == "Tomato"]
    top = tom["market_key"].value_counts().head(3).index.tolist()
    names = _market_names(top)
    viz.style()
    height = 5.0
    fig, axes = plt.subplots(1, 3, figsize=(13, height), sharey=True)
    viz.header(
        fig,
        "Stress test: forecasting the July 2023 tomato spike",
        "Trained only on data before 2023-07-01; 7-day-ahead forecasts plotted on the target date",
    )
    for ax, mk in zip(axes, top, strict=True):
        actual = prices[
            (prices["market_key"] == mk)
            & (prices["commodity"] == "Tomato")
            & (prices["date"] >= "2023-06-01")
            & (prices["date"] <= "2023-09-15")
        ]
        p = tom[tom["market_key"] == mk].sort_values("target_date")
        ax.fill_between(
            p["target_date"],
            p["model_p10"],
            p["model_p90"],
            color=viz.SEQUENTIAL[0],
            linewidth=0,
            label="model p10-p90",
        )
        ax.plot(actual["date"], actual["price"], color=viz.INK, linewidth=1.6, label="actual")
        ax.plot(
            p["target_date"],
            p["model_p50"],
            color=viz.COMMODITY_COLORS["Tomato"],
            label="model (p50)",
        )
        ax.plot(
            p["target_date"],
            p["baseline_last_value"],
            color=viz.COMMODITY_COLORS["Onion"],
            linewidth=1.4,
            label="baseline: last value",
        )
        ax.set_title(names.get(mk, mk), loc="left", fontsize=10, color=viz.INK_2)
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
        ax.set_ylim(0)
    axes[0].set_ylabel("Rs / quintal")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper left",
        bbox_to_anchor=(0.01, 1 - 0.72 / height),
        ncols=4,
        frameon=False,
        fontsize=9.5,
    )
    fig._mp_top = 1 - 1.05 / height
    viz.save(
        fig,
        "ml_stress_test_tomato_jul2023",
        note="Actual = real reports. Band = model p10-p90. Baseline = last known price.",
    )


def _market_names(keys: list[str]) -> dict:
    from mandipulse.queries import run_sql

    if not keys:
        return {}
    quoted = ", ".join(f"'{k}'" for k in keys)
    df = run_sql(
        f"select market_key, market || ' (' || district || ', ' || state || ')' as name "
        f"from marts.dim_market where market_key in ({quoted})"
    )
    return dict(zip(df["market_key"], df["name"], strict=True))


if __name__ == "__main__":
    print(json.dumps(train_forecast()["walk_forward"]["overall"], indent=2))
