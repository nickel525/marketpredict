from __future__ import annotations

import numpy as np
import pandas as pd

from marketpredict.features.engineer import _add_price_features, _add_target


def _panel() -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-02", periods=320)
    rng = np.random.default_rng(0)
    rows = []
    for ticker in ("AAA", "BBB"):
        price = 100.0
        for date in dates:
            price = max(5.0, price * (1 + rng.normal(0.0005, 0.015)))
            rows.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "open": price * 0.999,
                    "high": price * 1.01,
                    "low": price * 0.99,
                    "close": price,
                    "volume": 1_000_000.0,
                    "sector": "Information Technology",
                    "name": ticker,
                }
            )
    return pd.DataFrame(rows)


def test_features_at_t_ignore_future_prices() -> None:
    df = _panel()
    cutoff = df["date"].unique()[240]
    baseline = _add_price_features(df.copy())
    mutated = df.copy()
    future = mutated["date"] > cutoff
    mutated.loc[future, "close"] *= 8
    mutated.loc[future, "high"] *= 8
    mutated.loc[future, "low"] *= 8
    mutated.loc[future, "open"] *= 8
    mutated.loc[future, "volume"] *= 8
    leaked = _add_price_features(mutated)

    cols = [
        "ret_1d",
        "ret_5d",
        "ret_10d",
        "ret_20d",
        "momentum_60d",
        "rsi_14",
        "sma_10_ratio",
        "sma_20_ratio",
        "sma_50_ratio",
        "dist_52w_high",
        "gap",
        "volatility_20d",
        "rel_volume",
        "log_dollar_volume",
    ]
    left = baseline.loc[baseline["date"] == cutoff, ["ticker", *cols]].reset_index(drop=True)
    right = leaked.loc[leaked["date"] == cutoff, ["ticker", *cols]].reset_index(drop=True)
    pd.testing.assert_frame_equal(left, right, rtol=1e-10, atol=1e-10)


def test_target_uses_future_price() -> None:
    df = _add_price_features(_panel())
    labeled = _add_target(df.copy())
    cutoff = labeled["date"].unique()[240]
    mutated = df.copy()
    future = mutated["date"] > cutoff
    mutated.loc[future, "close"] *= 3
    relabeled = _add_target(mutated)
    before = labeled.loc[labeled["date"] == cutoff, ["ticker", "fwd_return_5d", "target"]].reset_index(drop=True)
    after = relabeled.loc[relabeled["date"] == cutoff, ["ticker", "fwd_return_5d", "target"]].reset_index(drop=True)
    assert not np.allclose(before["fwd_return_5d"], after["fwd_return_5d"])
