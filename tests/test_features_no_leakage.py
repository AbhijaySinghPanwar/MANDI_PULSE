"""No feature at day t may use data after t; regional features may only use t-1; targets are real
reports. Synthetic, test-only prices."""

import numpy as np
import pandas as pd
import pytest

from mandipulse.ml.features import CRASH_EXTRA_FEATURES, FORECAST_FEATURES, add_features, daily_grid

T = pd.Timestamp("2024-03-01")
FEATURES = [f for f in FORECAST_FEATURES + CRASH_EXTRA_FEATURES if f != "hist_crash_rate"]


def synthetic_prices(seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for m in range(4):  # four markets in one state, one in another state
        state = "S1" if m < 3 else "S2"
        for d in pd.date_range("2023-01-01", "2024-06-30"):
            if rng.random() < 0.3:  # markets skip days
                continue
            rows.append(
                {
                    "market_key": f"m{m}",
                    "commodity_key": 1,
                    "commodity": "Tomato",
                    "state": state,
                    "date": d,
                    "price": 1000 * rng.uniform(0.8, 1.2),
                }
            )
    return pd.DataFrame(rows)


def features(prices: pd.DataFrame) -> pd.DataFrame:
    return add_features(daily_grid(prices), ffill_limit=3, horizon=7)


def frame_until(f: pd.DataFrame, market: str, day: pd.Timestamp) -> pd.DataFrame:
    sel = f[(f["market_key"] == market) & (f["date"] <= day)].sort_values("date")
    return sel[["date", *FEATURES]].reset_index(drop=True)


def test_future_prices_do_not_change_features():
    base = synthetic_prices()
    shocked = base.copy()
    future = shocked["date"] > T
    shocked.loc[future, "price"] *= 7  # wild change after t, all markets
    a, b = features(base), features(shocked)
    for m in ["m0", "m1", "m3"]:
        pd.testing.assert_frame_equal(frame_until(a, m, T), frame_until(b, m, T), check_dtype=False)


def test_regional_features_only_use_previous_day():
    base = synthetic_prices()
    shocked = base.copy()
    # change OTHER markets' prices on day t itself: market m0's features at t must not move
    same_day_others = (shocked["date"] == T) & (shocked["market_key"] != "m0")
    shocked.loc[same_day_others, "price"] *= 5
    a, b = features(base), features(shocked)
    pd.testing.assert_frame_equal(
        frame_until(a, "m0", T), frame_until(b, "m0", T), check_dtype=False
    )


def test_target_is_always_a_real_report():
    prices = synthetic_prices()
    f = features(prices)
    has_target = f[f["target_price"].notna()]
    reported = prices.set_index(["market_key", "date"])["price"]
    keys = list(zip(has_target["market_key"], has_target["target_date"], strict=True))
    assert reported.reindex(keys).notna().all()
    assert np.allclose(reported.reindex(keys).to_numpy(), has_target["target_price"].to_numpy())


def test_no_target_when_target_day_has_no_report():
    prices = synthetic_prices()
    f = features(prices)
    reported = set(zip(prices["market_key"], prices["date"], strict=True))
    no_report = [
        (m, d) not in reported for m, d in zip(f["market_key"], f["target_date"], strict=True)
    ]
    assert f.loc[no_report, "target_price"].isna().all()


def test_filled_values_feed_features_but_are_limited():
    prices = synthetic_prices()
    f = features(prices)
    # a feature value may exist on a non-report day (forward fill) but never > 3 days after a report
    assert (f.loc[f["lp_t"].notna(), "days_since_last_report"] <= 3).all()


@pytest.mark.parametrize("col", ["d_lag_7", "roll_mean_30_rel", "report_freq_30"])
def test_feature_columns_exist(col):
    assert col in features(synthetic_prices()).columns
