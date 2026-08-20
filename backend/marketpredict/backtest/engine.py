from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from marketpredict.backtest.metrics import performance_metrics
from marketpredict.config import settings
from marketpredict.data.store import Store
from marketpredict.model.train import precision_at_k

logger = logging.getLogger(__name__)


def run_backtest(store: Store | None = None, top_k: int | None = None, cost_bps: float | None = None) -> dict[str, Any]:
    """Weekly top-K equal-weight strategy on walk-forward OOS predictions only."""
    store = store or Store()
    top_k = top_k or settings.top_k
    cost_bps = settings.cost_bps if cost_bps is None else cost_bps

    oos = store.read_parquet("predictions", "oos.parquet")
    ohlcv = store.read_parquet("raw", "ohlcv.parquet")
    oos["date"] = pd.to_datetime(oos["date"]).dt.tz_localize(None)
    ohlcv["date"] = pd.to_datetime(ohlcv["date"]).dt.tz_localize(None)

    ranking_metrics = precision_at_k(oos)
    all_dates = np.array(sorted(oos["date"].unique()))
    rebalance_dates = all_dates[:: settings.horizon_days]

    spy = (
        ohlcv[ohlcv["ticker"] == settings.spy_ticker][["date", "close"]]
        .drop_duplicates("date")
        .sort_values("date")
        .reset_index(drop=True)
    )

    rng = np.random.default_rng(settings.random_seed)
    weeks: list[dict[str, Any]] = []
    prev_weights: dict[str, float] = {}
    prev_random_weights: dict[str, float] = {}

    for i, date in enumerate(rebalance_dates):
        day = oos[oos["date"] == date].dropna(subset=["fwd_return_5d", "probability"])
        if len(day) < top_k:
            continue
        top = day.nlargest(top_k, "probability")
        tickers = top["ticker"].tolist()
        gross = float(top["fwd_return_5d"].mean())
        weights = {ticker: 1.0 / top_k for ticker in tickers}
        traded = sum(abs(weights.get(t, 0.0) - prev_weights.get(t, 0.0)) for t in set(weights) | set(prev_weights))
        cost = traded * (cost_bps / 10_000.0)
        net = gross - cost
        prev_weights = weights

        rand_idx = rng.choice(len(day), size=top_k, replace=False)
        random_pick = day.iloc[rand_idx]
        random_tickers = random_pick["ticker"].tolist()
        random_gross = float(random_pick["fwd_return_5d"].mean())
        random_weights = {ticker: 1.0 / top_k for ticker in random_tickers}
        random_traded = sum(
            abs(random_weights.get(t, 0.0) - prev_random_weights.get(t, 0.0))
            for t in set(random_weights) | set(prev_random_weights)
        )
        random_net = random_gross - random_traded * (cost_bps / 10_000.0)
        prev_random_weights = random_weights

        spy_ret = _forward_return(spy, date, settings.horizon_days)
        weeks.append(
            {
                "date": str(pd.Timestamp(date).date()),
                "tickers": tickers,
                "gross_return": gross,
                "net_return": net,
                "cost": cost,
                "random_return": random_net,
                "spy_return": spy_ret,
                "hit_5pct": gross >= settings.target_return,
            }
        )

    if not weeks:
        raise RuntimeError("Backtest produced no weekly periods.")

    weekly = pd.DataFrame(weeks)
    weekly["date"] = pd.to_datetime(weekly["date"])
    equity = _compound(weekly, spy)

    strategy = performance_metrics(weekly["gross_return"], equity["strategy"])
    strategy_net = performance_metrics(weekly["net_return"], equity["strategy_net"])
    spy_metrics = performance_metrics(weekly["spy_return"].fillna(0.0), equity["spy"])
    random_metrics = performance_metrics(weekly["random_return"], equity["random"])

    result = {
        "config": {
            "top_k": top_k,
            "hold_days": settings.horizon_days,
            "cost_bps_per_side": cost_bps,
            "n_weeks": int(len(weekly)),
            "start": str(weekly["date"].min().date()),
            "end": str(weekly["date"].max().date()),
        },
        "model": ranking_metrics,
        "strategy": strategy,
        "strategy_net": strategy_net,
        "spy": spy_metrics,
        "random": random_metrics,
        "equity_curve": [
            {
                "date": str(pd.Timestamp(row.date).date()),
                "strategy": float(row.strategy),
                "strategy_net": float(row.strategy_net),
                "spy": float(row.spy),
                "random": float(row.random),
            }
            for row in equity.itertuples(index=False)
        ],
        "weeks": weeks,
    }
    store.write_json(result, "backtest", "results.json")
    store.write_parquet(equity, "backtest", "equity_curve.parquet")
    logger.info(
        "Backtest weeks=%s CAGR=%.3f Sharpe=%.2f MaxDD=%.3f",
        len(weekly),
        strategy["cagr"],
        strategy["sharpe"],
        strategy["max_drawdown"],
    )
    return result


def _forward_return(prices: pd.DataFrame, date: pd.Timestamp, horizon: int) -> float:
    idx = int(prices["date"].searchsorted(date))
    if idx < 0 or idx + horizon >= len(prices):
        return float("nan")
    start = float(prices.iloc[idx]["close"])
    end = float(prices.iloc[idx + horizon]["close"])
    if start <= 0:
        return float("nan")
    return end / start - 1


def _compound(weekly: pd.DataFrame, spy: pd.DataFrame) -> pd.DataFrame:
    first_date = weekly["date"].iloc[0]
    spy_start = _price_on_or_after(spy, first_date, 0)
    rows = [
        {
            "date": first_date,
            "strategy": 1.0,
            "strategy_net": 1.0,
            "spy": 1.0,
            "random": 1.0,
        }
    ]
    strat = 1.0
    strat_net = 1.0
    rand = 1.0
    for row in weekly.itertuples(index=False):
        strat *= 1.0 + float(row.gross_return)
        strat_net *= 1.0 + float(row.net_return)
        rand *= 1.0 + float(row.random_return)
        exit_px = _price_on_or_after(spy, row.date, settings.horizon_days)
        spy_eq = float(exit_px) / float(spy_start) if spy_start else float("nan")
        exit_date = _date_on_or_after(spy, row.date, settings.horizon_days)
        rows.append(
            {
                "date": exit_date if exit_date is not None else row.date,
                "strategy": strat,
                "strategy_net": strat_net,
                "spy": spy_eq,
                "random": rand,
            }
        )
    return pd.DataFrame(rows)


def _price_on_or_after(prices: pd.DataFrame, date: pd.Timestamp, offset: int) -> float:
    idx = int(prices["date"].searchsorted(date))
    if idx < 0 or idx + offset >= len(prices):
        return float("nan")
    return float(prices.iloc[idx + offset]["close"])


def _date_on_or_after(prices: pd.DataFrame, date: pd.Timestamp, offset: int) -> pd.Timestamp | None:
    idx = int(prices["date"].searchsorted(date))
    if idx < 0 or idx + offset >= len(prices):
        return None
    return pd.Timestamp(prices.iloc[idx + offset]["date"])
