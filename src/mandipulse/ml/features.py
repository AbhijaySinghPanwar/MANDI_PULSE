"""Leakage-free features for the forecast (Model A) and crash (Model B) models (spec 9.1, 9.2).

Rules (enforced by tests/test_features_no_leakage.py):
  * Every feature at day t uses only data dated <= t. Regional (state) features use t-1.
  * Forward-filling (limit = ml.ffill_limit_days) is used for FEATURES only.
  * Targets are REAL reports: the forecast target is the observed price on t + horizon; if there is
    no report that day the row has no target. A filled value is never a target.

Layout: one row per series (market x commodity) per calendar day between its first and last
report ("daily grid"). price_obs is the real report (NaN if none that day).
"""

import numpy as np
import pandas as pd

LAGS = (1, 3, 7, 14, 28)
WINDOWS = (7, 14, 30)

FORECAST_FEATURES = [
    "lp_t",
    *[f"d_lag_{k}" for k in LAGS],
    *[f"roll_mean_{w}_rel" for w in WINDOWS],
    *[f"roll_std_{w}" for w in WINDOWS],
    *[f"roll_min_{w}_rel" for w in WINDOWS],
    *[f"roll_max_{w}_rel" for w in WINDOWS],
    "momentum_30",
    "yoy_change",
    "days_since_last_report",
    "report_freq_30",
    "state_rel_prev1",
    "state_change_7_prev1",
    "state_n_markets_prev1",
    "dow",
    "month",
    "week_of_year",
    "commodity",
    "state",
    "market_key",
]
CRASH_EXTRA_FEATURES = ["slope_7", "slope_14", "state_share_falling_prev1", "hist_crash_rate"]
CATEGORICAL = ["commodity", "state", "market_key"]


def daily_grid(prices: pd.DataFrame) -> pd.DataFrame:
    """One row per series per day from its first to last report; price_obs = real report or NaN."""
    p = prices.sort_values(["market_key", "commodity_key", "date"])
    p = p.assign(series_id=p.groupby(["market_key", "commodity_key"], sort=False).ngroup())
    spans = p.groupby("series_id")["date"].agg(["min", "max"])
    lengths = ((spans["max"] - spans["min"]).dt.days + 1).to_numpy()
    sid = np.repeat(spans.index.to_numpy(), lengths)
    offsets = np.concatenate([np.arange(n) for n in lengths])
    dates = np.repeat(spans["min"].to_numpy(), lengths) + offsets.astype("timedelta64[D]")
    grid = pd.DataFrame({"series_id": sid, "date": dates})
    meta = p.drop_duplicates("series_id")[
        ["series_id", "market_key", "commodity_key", "commodity", "state"]
    ]
    grid = grid.merge(meta, on="series_id", how="left")
    grid = grid.merge(p[["series_id", "date", "price"]], on=["series_id", "date"], how="left")
    grid = grid.rename(columns={"price": "price_obs"})
    grid["reported"] = grid["price_obs"].notna()
    return grid.sort_values(["series_id", "date"]).reset_index(drop=True)


def _regional(grid: pd.DataFrame) -> pd.DataFrame:
    """State x commodity x day aggregates from REAL reports, then shifted to t-1."""
    rep = grid[grid["reported"]]
    day = (
        rep.groupby(["state", "commodity", "date"])
        .agg(
            state_lp=("lp_obs", "median"),
            state_n=("lp_obs", "size"),
            share_falling=(
                "slope_7_obs",
                lambda s: (s.dropna() < 0).mean() if s.notna().any() else np.nan,
            ),
        )
        .reset_index()
    )
    out = []
    for (state, com), g in day.groupby(["state", "commodity"], sort=False):
        idx = pd.date_range(g["date"].min(), g["date"].max() + pd.Timedelta(days=1), freq="D")
        g = g.set_index("date").reindex(idx)
        # value known at the END of day d is used on day d+1  ->  shift(1) on a daily calendar
        prev1 = g.shift(1)
        res = pd.DataFrame(
            {
                "date": idx,
                "state": state,
                "commodity": com,
                "state_lp_prev1": prev1["state_lp"].ffill(limit=3),
                "state_n_markets_prev1": prev1["state_n"].fillna(0),
                "state_share_falling_prev1": prev1["share_falling"],
            }
        )
        res["state_change_7_prev1"] = res["state_lp_prev1"] - res["state_lp_prev1"].shift(7)
        out.append(res)
    return pd.concat(out, ignore_index=True)


def add_features(grid: pd.DataFrame, ffill_limit: int = 3, horizon: int = 7) -> pd.DataFrame:
    """Leakage-safe features at each anchor day t (only data up to t) plus the t+horizon target."""
    g = grid.sort_values(["series_id", "date"]).reset_index(drop=True).copy()
    by = g.groupby("series_id", sort=False)
    g["lp_obs"] = np.log(g["price_obs"])
    g["lp_t"] = by["lp_obs"].ffill(limit=ffill_limit)  # feature-only fill
    last_rep = g["date"].where(g["reported"])
    g["days_since_last_report"] = (g["date"] - last_rep.groupby(g["series_id"]).ffill()).dt.days
    by = g.groupby("series_id", sort=False)

    for k in LAGS:
        g[f"lag_{k}"] = by["lp_t"].shift(k)
        g[f"d_lag_{k}"] = g["lp_t"] - g[f"lag_{k}"]
    for w in WINDOWS:
        roll = by["lp_obs"].rolling(w, min_periods=1)
        g[f"roll_mean_{w}"] = roll.mean().reset_index(level=0, drop=True)
        g[f"roll_std_{w}"] = (
            by["lp_obs"].rolling(w, min_periods=2).std().reset_index(level=0, drop=True)
        )
        g[f"roll_min_{w}_rel"] = roll.min().reset_index(level=0, drop=True) - g["lp_t"]
        g[f"roll_max_{w}_rel"] = roll.max().reset_index(level=0, drop=True) - g["lp_t"]
        g[f"roll_mean_{w}_rel"] = g[f"roll_mean_{w}"] - g["lp_t"]
    g["momentum_30"] = g["lp_t"] - g["roll_mean_30"]
    g["yoy_change"] = g["lp_t"] - by["lp_t"].shift(364)
    g["report_freq_30"] = (
        by["reported"]
        .rolling(30, min_periods=1)
        .sum()
        .reset_index(level=0, drop=True)
        .astype(float)
    )
    g["slope_7"] = g["d_lag_7"]
    g["slope_14"] = g["d_lag_14"]
    # 7-day change on REAL reports only (input to the state "share falling" at t-1)
    g["slope_7_obs"] = g["lp_obs"] - by["lp_t"].shift(7)
    g["price_ma7"] = (
        by["price_obs"].rolling(7, min_periods=1).mean().reset_index(level=0, drop=True)
    )

    reg = _regional(g)
    g = g.merge(reg, on=["state", "commodity", "date"], how="left")
    g["state_rel_prev1"] = g["lp_t"] - g["state_lp_prev1"]

    target_date = g["date"] + pd.Timedelta(days=horizon)
    g["target_date"] = target_date
    g["dow"] = target_date.dt.dayofweek
    g["month"] = target_date.dt.month
    g["week_of_year"] = target_date.dt.isocalendar().week.astype(int)

    # Forecast target: the REAL report on t + horizon (never a filled value)
    g = g.sort_values(["series_id", "date"]).reset_index(drop=True)
    by = g.groupby("series_id", sort=False)
    g["target_lp"] = by["lp_obs"].shift(-horizon)
    g["target_price"] = by["price_obs"].shift(-horizon)
    g.loc[g["target_date"] != by["date"].shift(-horizon), ["target_lp", "target_price"]] = np.nan
    return g


def as_model_frame(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Feature matrix with LightGBM-ready categoricals."""
    x = df[columns].copy()
    for c in CATEGORICAL:
        if c in x:
            x[c] = x[c].astype("category")
    return x
