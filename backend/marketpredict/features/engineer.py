from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from marketpredict.config import settings
from marketpredict.data.collector import SECTOR_ETFS
from marketpredict.data.store import Store

logger = logging.getLogger(__name__)

FEATURE_COLUMNS = [
    "ret_1d",
    "ret_5d",
    "ret_10d",
    "ret_20d",
    "momentum_60d",
    "volume_change",
    "rel_volume",
    "volatility_20d",
    "rsi_14",
    "sma_10_ratio",
    "sma_20_ratio",
    "sma_50_ratio",
    "dist_52w_high",
    "gap",
    "rel_spy_20d",
    "rel_sector_20d",
    "log_dollar_volume",
    "days_to_earnings",
    "days_since_earnings",
]

FRIENDLY_NAMES = {
    "ret_1d": "1-day return",
    "ret_5d": "5-day return",
    "ret_10d": "10-day return",
    "ret_20d": "20-day return",
    "momentum_60d": "60-day momentum",
    "volume_change": "volume change",
    "rel_volume": "relative volume",
    "volatility_20d": "20-day volatility",
    "rsi_14": "14-day RSI",
    "sma_10_ratio": "distance from 10-day MA",
    "sma_20_ratio": "distance from 20-day MA",
    "sma_50_ratio": "distance from 50-day MA",
    "dist_52w_high": "distance from 52-week high",
    "gap": "overnight gap",
    "rel_spy_20d": "20-day return vs S&P 500",
    "rel_sector_20d": "20-day return vs sector",
    "log_dollar_volume": "log dollar volume",
    "days_to_earnings": "days until earnings",
    "days_since_earnings": "days since earnings",
}


def build_feature_frame(store: Store | None = None) -> pd.DataFrame:
    """Build point-in-time features. Values on date T use only data at or before T."""
    store = store or Store()
    ohlcv = store.read_parquet("raw", "ohlcv.parquet")
    universe = store.read_parquet("raw", "universe.parquet")
    earnings = (
        store.read_parquet("raw", "earnings.parquet")
        if store.exists("raw", "earnings.parquet")
        else pd.DataFrame(columns=["ticker", "earnings_date"])
    )

    ohlcv["date"] = pd.to_datetime(ohlcv["date"]).dt.tz_localize(None)
    ohlcv = ohlcv.sort_values(["ticker", "date"]).drop_duplicates(["ticker", "date"])

    spy = ohlcv[ohlcv["ticker"] == settings.spy_ticker][["date", "close"]].rename(columns={"close": "spy_close"})
    panel = ohlcv.merge(universe[["ticker", "sector", "name"]], on="ticker", how="left")
    stock_panel = panel[panel["ticker"] != settings.spy_ticker].copy()
    stock_panel = stock_panel[~stock_panel["ticker"].isin(SECTOR_ETFS.values())].copy()

    stock_panel = _add_price_features(stock_panel)
    stock_panel = _add_spy_relative(stock_panel, spy)
    stock_panel = _add_sector_relative(stock_panel)
    stock_panel = _add_earnings_features(stock_panel, earnings)
    stock_panel = _add_target(stock_panel)

    required = ["ret_1d", "ret_5d", "ret_20d", "rsi_14", "sma_20_ratio", "dist_52w_high", "rel_spy_20d"]
    before = len(stock_panel)
    stock_panel = stock_panel.dropna(subset=required).reset_index(drop=True)
    logger.info("Feature rows %s -> %s after dropping incomplete history", before, len(stock_panel))

    store.write_parquet(stock_panel, "features", "features.parquet")
    return stock_panel


def _add_price_features(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("ticker", sort=False)
    close = df["close"]

    df["ret_1d"] = g["close"].pct_change(1)
    df["ret_5d"] = g["close"].pct_change(5)
    df["ret_10d"] = g["close"].pct_change(10)
    df["ret_20d"] = g["close"].pct_change(20)
    df["momentum_60d"] = g["close"].pct_change(60)

    df["volume_change"] = g["volume"].pct_change(1).replace([np.inf, -np.inf], np.nan)
    vol_ma20 = g["volume"].transform(lambda s: s.rolling(20, min_periods=10).mean())
    df["rel_volume"] = df["volume"] / vol_ma20.replace(0, np.nan)
    df["volatility_20d"] = g["close"].transform(
        lambda s: s.pct_change().rolling(20, min_periods=10).std()
    )

    df["rsi_14"] = g["close"].transform(_rsi)
    df["sma_10_ratio"] = close / g["close"].transform(lambda s: s.rolling(10, min_periods=10).mean()) - 1
    df["sma_20_ratio"] = close / g["close"].transform(lambda s: s.rolling(20, min_periods=20).mean()) - 1
    df["sma_50_ratio"] = close / g["close"].transform(lambda s: s.rolling(50, min_periods=50).mean()) - 1

    high_52w = g["high"].transform(lambda s: s.rolling(252, min_periods=180).max())
    df["dist_52w_high"] = close / high_52w - 1

    prev_close = g["close"].shift(1)
    df["gap"] = df["open"] / prev_close - 1
    df["log_dollar_volume"] = np.log((df["close"] * df["volume"]).clip(lower=1.0))
    return df


def _rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _add_spy_relative(df: pd.DataFrame, spy: pd.DataFrame) -> pd.DataFrame:
    spy = spy.sort_values("date").drop_duplicates("date")
    spy["spy_ret_20d"] = spy["spy_close"].pct_change(20)
    merged = df.merge(spy[["date", "spy_close", "spy_ret_20d"]], on="date", how="left")
    merged["rel_spy_20d"] = merged["ret_20d"] - merged["spy_ret_20d"]
    return merged


def _add_sector_relative(df: pd.DataFrame) -> pd.DataFrame:
    grouped = df.groupby(["date", "sector"], dropna=False)["ret_20d"]
    count = grouped.transform("count")
    total = grouped.transform("sum")
    sector_ex_self = (total - df["ret_20d"]) / (count - 1).clip(lower=1)
    df["rel_sector_20d"] = df["ret_20d"] - sector_ex_self
    df.loc[count <= 1, "rel_sector_20d"] = 0.0
    return df


def _add_earnings_features(df: pd.DataFrame, earnings: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["days_to_earnings"] = np.nan
    df["days_since_earnings"] = np.nan
    if earnings is None or earnings.empty:
        return df

    events = earnings.dropna().copy()
    events["earnings_date"] = pd.to_datetime(events["earnings_date"]).dt.tz_localize(None)
    earn_map = {
        ticker: np.sort(grp["earnings_date"].to_numpy())
        for ticker, grp in events.groupby("ticker", sort=False)
    }
    parts = []
    for ticker, grp in df.groupby("ticker", sort=False):
        grp = grp.copy()
        if "ticker" not in grp.columns:
            grp.insert(0, "ticker", ticker)
        ev = earn_map.get(ticker)
        if ev is None or len(ev) == 0:
            parts.append(grp)
            continue
        dates = pd.to_datetime(grp["date"]).to_numpy()
        nxt = np.searchsorted(ev, dates, side="left")
        prev = nxt - 1
        next_dates = np.array([ev[i] if i < len(ev) else np.datetime64("NaT") for i in nxt])
        prev_dates = np.array([ev[i] if i >= 0 else np.datetime64("NaT") for i in prev])
        grp["days_to_earnings"] = (pd.to_datetime(next_dates) - pd.to_datetime(dates)) / pd.Timedelta(days=1)
        grp["days_since_earnings"] = (pd.to_datetime(dates) - pd.to_datetime(prev_dates)) / pd.Timedelta(days=1)
        parts.append(grp)
    return pd.concat(parts, ignore_index=True)


def _add_target(df: pd.DataFrame) -> pd.DataFrame:
    future_close = df.groupby("ticker", sort=False)["close"].shift(-settings.horizon_days)
    df["fwd_return_5d"] = future_close / df["close"] - 1
    df["target"] = np.where(
        df["fwd_return_5d"].isna(),
        np.nan,
        (df["fwd_return_5d"] >= settings.target_return).astype(float),
    )
    return df
