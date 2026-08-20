from __future__ import annotations

import math
from typing import Any

import pandas as pd

from marketpredict.data.store import Store
from marketpredict.features.engineer import FEATURE_COLUMNS, FRIENDLY_NAMES

store = Store()


def missing_artifact_detail(exc: FileNotFoundError) -> str:
    return (
        f"{exc}. Run the pipeline first: collect_data.py, build_features.py, "
        "train.py, then run_backtest.py."
    )


def load_rankings(limit: int = 50) -> dict[str, Any]:
    latest = store.read_parquet("predictions", "latest.parquet")
    fundamentals = (
        store.read_parquet("raw", "fundamentals.parquet")
        if store.exists("raw", "fundamentals.parquet")
        else pd.DataFrame(columns=["ticker", "market_cap"])
    )
    meta = store.read_json("models", "meta.json")
    latest["date"] = pd.to_datetime(latest["date"])
    ranked = latest.sort_values("probability", ascending=False).head(limit)
    if "market_cap" in fundamentals.columns:
        ranked = ranked.merge(fundamentals[["ticker", "market_cap"]], on="ticker", how="left")
    rows = []
    for i, row in enumerate(ranked.itertuples(index=False), start=1):
        rows.append(
            {
                "rank": i,
                "ticker": row.ticker,
                "name": getattr(row, "name", row.ticker),
                "probability": _num(row.probability),
                "price": _num(row.close, 2),
                "momentum": _num(getattr(row, "momentum_60d", getattr(row, "ret_20d", None))),
                "ret_5d": _num(getattr(row, "ret_5d", None)),
                "volume": _num(getattr(row, "volume", None), 0),
                "rel_volume": _num(getattr(row, "rel_volume", None)),
                "sector": getattr(row, "sector", None) or "Unknown",
                "market_cap": _num(getattr(row, "market_cap", None)),
            }
        )
    return {
        "as_of": str(pd.Timestamp(latest["date"].max()).date()),
        "collected_at": _raw_meta().get("collected_at"),
        "scored_at": meta.get("scored_at"),
        "positive_rate": meta.get("positive_rate"),
        "ranking_metrics": meta.get("ranking_metrics", {}),
        "stocks": rows,
    }


def load_status() -> dict[str, Any]:
    raw = _raw_meta()
    model = store.read_json("models", "meta.json") if store.exists("models", "meta.json") else {}
    latest_date = None
    if store.exists("predictions", "latest.parquet"):
        latest = store.read_parquet("predictions", "latest.parquet")
        latest_date = str(pd.to_datetime(latest["date"]).max().date())
    return {
        "price_as_of": latest_date or raw.get("latest_bar") or model.get("latest_date"),
        "collected_at": raw.get("collected_at"),
        "scored_at": model.get("scored_at"),
        "n_tickers": raw.get("n_tickers"),
        "source": raw.get("source"),
        "mode": raw.get("mode", "full"),
    }


def _raw_meta() -> dict[str, Any]:
    if store.exists("raw", "meta.json"):
        return store.read_json("raw", "meta.json")
    return {}


def load_stock_detail(ticker: str) -> dict[str, Any]:
    ticker = ticker.upper()
    latest = store.read_parquet("predictions", "latest.parquet")
    latest["date"] = pd.to_datetime(latest["date"])
    row = latest[latest["ticker"].str.upper() == ticker]
    if row.empty:
        raise KeyError(f"No prediction available for {ticker}")
    stock = row.iloc[0]
    ohlcv = store.read_parquet("raw", "ohlcv.parquet")
    ohlcv["date"] = pd.to_datetime(ohlcv["date"])
    history = (
        ohlcv[ohlcv["ticker"].str.upper() == ticker]
        .sort_values("date")
        .tail(252)[["date", "open", "high", "low", "close", "volume"]]
    )
    contrib = (
        store.read_parquet("predictions", "latest_contributions.parquet")
        if store.exists("predictions", "latest_contributions.parquet")
        else pd.DataFrame()
    )
    features = []
    contrib_row = None
    if not contrib.empty:
        match = contrib[contrib["ticker"].str.upper() == ticker]
        if not match.empty:
            contrib_row = match.iloc[0]
    for col in FEATURE_COLUMNS:
        value = stock[col] if col in stock.index else None
        contribution = contrib_row[col] if contrib_row is not None and col in contrib_row.index else None
        features.append(
            {
                "key": col,
                "label": FRIENDLY_NAMES.get(col, col),
                "value": _num(value),
                "contribution": _num(contribution),
            }
        )
    features = sorted(
        features,
        key=lambda item: abs(item["contribution"] or 0.0),
        reverse=True,
    )
    return {
        "ticker": ticker,
        "name": stock.get("name", ticker),
        "sector": stock.get("sector", "Unknown"),
        "as_of": str(pd.Timestamp(stock["date"]).date()),
        "probability": _num(stock["probability"]),
        "price": _num(stock["close"], 2),
        "volume": _num(stock.get("volume"), 0),
        "returns": {
            "1d": _num(stock.get("ret_1d")),
            "5d": _num(stock.get("ret_5d")),
            "10d": _num(stock.get("ret_10d")),
            "20d": _num(stock.get("ret_20d")),
            "60d": _num(stock.get("momentum_60d")),
        },
        "features": features,
        "explanation": _explain(stock, features),
        "history": [
            {
                "date": str(pd.Timestamp(item.date).date()),
                "open": _num(item.open, 2),
                "high": _num(item.high, 2),
                "low": _num(item.low, 2),
                "close": _num(item.close, 2),
                "volume": _num(item.volume, 0),
            }
            for item in history.itertuples(index=False)
        ],
    }


def load_backtest() -> dict[str, Any]:
    return store.read_json("backtest", "results.json")


def _explain(stock: pd.Series, features: list[dict[str, Any]]) -> str:
    positive = [f for f in features if (f["contribution"] or 0) > 0][:3]
    if not positive:
        return (
            f"{stock.get('ticker')} is ranked using the current feature snapshot, "
            "but no single feature dominated the score."
        )
    bits = []
    for item in positive:
        rendered = _format_feature(item)
        bits.append(f"{item['label']} ({rendered})")
    return (
        f"The model assigned a {float(stock['probability']) * 100:.1f}% probability of a 5%+ gain "
        f"over the next 5 trading days, driven mainly by {', '.join(bits)}."
    )


def _format_feature(item: dict[str, Any]) -> str:
    value = item["value"]
    if value is None:
        return "n/a"
    key = item["key"]
    if key == "rsi_14":
        return f"{value:.1f}"
    if key in {"rel_volume", "log_dollar_volume", "days_to_earnings", "days_since_earnings"}:
        return f"{value:.2f}"
    return f"{value:.1%}"


def _num(value: Any, digits: int | None = None) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    if digits is not None:
        return round(number, digits)
    return number
