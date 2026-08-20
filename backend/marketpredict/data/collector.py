from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import yfinance as yf

from marketpredict.config import settings
from marketpredict.data.store import Store
from marketpredict.data.universe import load_universe

logger = logging.getLogger(__name__)

SECTOR_ETFS = {
    "Information Technology": "XLK",
    "Financials": "XLF",
    "Health Care": "XLV",
    "Consumer Discretionary": "XLY",
    "Communication Services": "XLC",
    "Industrials": "XLI",
    "Consumer Staples": "XLP",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Materials": "XLB",
}


def collect_market_data(
    limit: int | None = None,
    start: str | None = None,
    refresh_universe: bool = False,
) -> dict[str, str]:
    """Download OHLCV, fundamentals, and earnings; persist parquet artifacts."""
    store = Store()
    settings.ensure_dirs()
    start = start or settings.start_date
    universe = load_universe(limit=limit, refresh=refresh_universe)
    tickers = universe["ticker"].tolist()
    extras = [settings.spy_ticker, *sorted(set(SECTOR_ETFS.values()))]
    all_tickers = list(dict.fromkeys(tickers + extras))

    logger.info("Downloading OHLCV for %s symbols from %s", len(all_tickers), start)
    ohlcv = _download_ohlcv(all_tickers, start)
    ohlcv = _filter_history(ohlcv, tickers)

    kept = sorted(ohlcv.loc[ohlcv["ticker"].isin(tickers), "ticker"].unique())
    universe = universe[universe["ticker"].isin(kept)].copy()
    logger.info("Universe after history filter: %s", len(universe))

    fundamentals = _download_fundamentals(universe)
    earnings = _download_earnings(kept)

    store.write_parquet(ohlcv, "raw", "ohlcv.parquet")
    store.write_parquet(universe, "raw", "universe.parquet")
    store.write_parquet(fundamentals, "raw", "fundamentals.parquet")
    store.write_parquet(earnings, "raw", "earnings.parquet")
    store.write_json(
        {
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "start": start,
            "n_tickers": len(kept),
            "n_rows": int(len(ohlcv)),
            "source": "yfinance",
        },
        "raw",
        "meta.json",
    )
    return {
        "ohlcv": str(store.path("raw", "ohlcv.parquet")),
        "universe": str(store.path("raw", "universe.parquet")),
        "fundamentals": str(store.path("raw", "fundamentals.parquet")),
        "earnings": str(store.path("raw", "earnings.parquet")),
    }


def refresh_market_data(
    overlap_days: int = 10,
    refresh_universe: bool = False,
    refresh_earnings: bool = False,
) -> dict[str, str]:
    """Pull the latest Yahoo bars and merge them into the stored panel.

    Re-downloads a short overlap window so today's in-progress bar and any
    late split/dividend adjustments replace stale rows. Does not rebuild
    the full 2018–present history unless no cache exists.
    """
    store = Store()
    if not store.exists("raw", "ohlcv.parquet"):
        logger.info("No cached OHLCV; running a full collect")
        return collect_market_data(refresh_universe=refresh_universe)

    existing = store.read_parquet("raw", "ohlcv.parquet")
    existing["date"] = pd.to_datetime(existing["date"]).dt.tz_localize(None)
    last = existing["date"].max()
    start = (pd.Timestamp(last) - pd.Timedelta(days=overlap_days)).strftime("%Y-%m-%d")

    universe = load_universe(refresh=refresh_universe)
    tickers = universe["ticker"].tolist()
    extras = [settings.spy_ticker, *sorted(set(SECTOR_ETFS.values()))]
    all_tickers = list(dict.fromkeys(tickers + extras))

    logger.info("Refreshing OHLCV from %s (last stored bar %s)", start, pd.Timestamp(last).date())
    new = _download_ohlcv(all_tickers, start)
    if new.empty:
        raise RuntimeError("Yahoo Finance returned no new bars. Check network and try again.")

    cutoff = pd.Timestamp(start)
    kept_old = existing[existing["date"] < cutoff]
    ohlcv = pd.concat([kept_old, new], ignore_index=True)
    ohlcv = ohlcv.drop_duplicates(["ticker", "date"], keep="last")
    ohlcv = ohlcv.sort_values(["ticker", "date"]).reset_index(drop=True)
    ohlcv = _filter_history(ohlcv, tickers)

    kept = sorted(ohlcv.loc[ohlcv["ticker"].isin(tickers), "ticker"].unique())
    universe = universe[universe["ticker"].isin(kept)].copy()
    fundamentals = _download_fundamentals(universe)
    if refresh_earnings:
        earnings = _download_earnings(kept)
    elif store.exists("raw", "earnings.parquet"):
        earnings = store.read_parquet("raw", "earnings.parquet")
    else:
        earnings = _download_earnings(kept)

    latest_bar = pd.to_datetime(ohlcv["date"]).max()
    store.write_parquet(ohlcv, "raw", "ohlcv.parquet")
    store.write_parquet(universe, "raw", "universe.parquet")
    store.write_parquet(fundamentals, "raw", "fundamentals.parquet")
    store.write_parquet(earnings, "raw", "earnings.parquet")
    store.write_json(
        {
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "start": settings.start_date,
            "n_tickers": len(kept),
            "n_rows": int(len(ohlcv)),
            "latest_bar": str(pd.Timestamp(latest_bar).date()),
            "source": "yfinance",
            "mode": "incremental",
        },
        "raw",
        "meta.json",
    )
    logger.info(
        "Stored panel through %s (%s rows, %s tickers)",
        pd.Timestamp(latest_bar).date(),
        len(ohlcv),
        len(kept),
    )
    return {
        "ohlcv": str(store.path("raw", "ohlcv.parquet")),
        "latest_bar": str(pd.Timestamp(latest_bar).date()),
        "n_tickers": str(len(kept)),
    }


def generate_synthetic_data(
    n_tickers: int = 40,
    n_days: int = 900,
    seed: int = 42,
) -> dict[str, str]:
    """Deterministic synthetic panel for offline tests and demos."""
    store = Store()
    settings.ensure_dirs()
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n_days)
    sectors = [
        "Information Technology",
        "Financials",
        "Health Care",
        "Consumer Discretionary",
        "Energy",
        "Industrials",
    ]
    tickers = [f"T{i:03d}" for i in range(n_tickers)]
    rows = []
    universe_rows = []
    earnings_rows = []
    for i, ticker in enumerate(tickers):
        sector = sectors[i % len(sectors)]
        universe_rows.append(
            {"ticker": ticker, "name": f"Synthetic {ticker}", "sector": sector, "industry": "", "source": "synthetic"}
        )
        price = 50 + rng.uniform(0, 80)
        vol_scale = rng.uniform(0.012, 0.035)
        for date in dates:
            ret = rng.normal(0.0004, vol_scale)
            if rng.random() < 0.03:
                ret += rng.uniform(0.04, 0.09)
            gap = rng.normal(0, 0.004)
            open_ = price * (1 + gap)
            close = max(1.0, price * (1 + ret))
            high = max(open_, close) * (1 + abs(rng.normal(0, 0.006)))
            low = min(open_, close) * (1 - abs(rng.normal(0, 0.006)))
            volume = float(rng.integers(800_000, 8_000_000))
            rows.append(
                {
                    "date": date.tz_localize(None) if date.tzinfo else date,
                    "ticker": ticker,
                    "open": open_,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                }
            )
            price = close
        for offset in range(80, n_days, 63):
            earnings_rows.append({"ticker": ticker, "earnings_date": dates[min(offset, n_days - 1)]})

    spy_price = 400.0
    spy_rows = []
    for date in dates:
        spy_price = max(10.0, spy_price * (1 + rng.normal(0.0003, 0.01)))
        spy_rows.append(
            {
                "date": date,
                "ticker": settings.spy_ticker,
                "open": spy_price,
                "high": spy_price * 1.005,
                "low": spy_price * 0.995,
                "close": spy_price,
                "volume": 80_000_000,
            }
        )

    ohlcv = pd.concat([pd.DataFrame(rows), pd.DataFrame(spy_rows)], ignore_index=True)
    universe = pd.DataFrame(universe_rows)
    fundamentals = pd.DataFrame(
        {
            "ticker": tickers,
            "name": [f"Synthetic {t}" for t in tickers],
            "sector": [sectors[i % len(sectors)] for i in range(n_tickers)],
            "market_cap": rng.uniform(5e9, 4e11, size=n_tickers),
        }
    )
    earnings = pd.DataFrame(earnings_rows)

    store.write_parquet(ohlcv, "raw", "ohlcv.parquet")
    store.write_parquet(universe, "raw", "universe.parquet")
    store.write_parquet(fundamentals, "raw", "fundamentals.parquet")
    store.write_parquet(earnings, "raw", "earnings.parquet")
    store.write_json({"collected_at": datetime.now(timezone.utc).isoformat(), "source": "synthetic"}, "raw", "meta.json")
    return {"ohlcv": str(store.path("raw", "ohlcv.parquet"))}


def _yahoo_end() -> str:
    """yfinance `end` is exclusive; pad by two UTC days so today's US session is included."""
    return (datetime.now(timezone.utc).date() + timedelta(days=2)).isoformat()


def _download_ohlcv(tickers: list[str], start: str) -> pd.DataFrame:
    end = _yahoo_end()
    logger.info("Yahoo download start=%s end=%s (end exclusive)", start, end)
    raw = yf.download(
        tickers=tickers,
        start=start,
        end=end,
        auto_adjust=True,
        threads=True,
        group_by="column",
        progress=True,
    )
    long = _ohlcv_to_long(raw)
    long = long.dropna(subset=["close"])
    long["date"] = pd.to_datetime(long["date"]).dt.tz_localize(None)
    long["ticker"] = long["ticker"].astype(str)
    for col in ("open", "high", "low", "close", "volume"):
        long[col] = pd.to_numeric(long[col], errors="coerce")
    return long.sort_values(["ticker", "date"]).reset_index(drop=True)


def _ohlcv_to_long(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["date", "ticker", "open", "high", "low", "close", "volume"])

    working = df.copy()
    if not isinstance(working.columns, pd.MultiIndex):
        working = working.copy()
        working["ticker"] = working.columns.name or "UNKNOWN"
        working = working.reset_index()
        working.columns = [str(c).lower().replace(" ", "_") for c in working.columns]
        date_col = "date" if "date" in working.columns else working.columns[0]
        working = working.rename(columns={date_col: "date"})
        return _select_ohlcv_cols(working)

    names = [str(n).lower() if n is not None else "" for n in working.columns.names]
    fields = {"open", "high", "low", "close", "adj_close", "adj close", "volume"}
    level0 = {str(v).lower() for v in working.columns.get_level_values(0).unique()}
    if "ticker" in names:
        ticker_level = names.index("ticker")
        working = working.stack(level=ticker_level, future_stack=True)
    elif level0 & fields:
        working = working.stack(level=1, future_stack=True)
    else:
        working = working.stack(level=0, future_stack=True)

    working = working.reset_index()
    working.columns = [str(c).lower().replace(" ", "_") for c in working.columns]
    rename = {}
    for col in working.columns:
        if col in {"date", "index", "level_0"} or "date" in col:
            if "ticker" not in col:
                rename[col] = "date" if col != "ticker" else col
        if col in {"level_1", "symbol"}:
            rename[col] = "ticker"
    working = working.rename(columns=rename)
    if "ticker" not in working.columns:
        for col in working.columns:
            if col not in {"date", "open", "high", "low", "close", "adj_close", "volume"}:
                if working[col].dtype == object:
                    working = working.rename(columns={col: "ticker"})
                    break
    if "date" not in working.columns:
        working = working.rename(columns={working.columns[0]: "date"})
    if "close" not in working.columns and "adj_close" in working.columns:
        working["close"] = working["adj_close"]
    return _select_ohlcv_cols(working)


def _select_ohlcv_cols(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["date", "ticker", "open", "high", "low", "close", "volume"]
    for col in cols:
        if col not in df.columns:
            df[col] = np.nan
    return df[cols]


def _filter_history(ohlcv: pd.DataFrame, universe_tickers: list[str]) -> pd.DataFrame:
    counts = ohlcv.groupby("ticker")["date"].size()
    keep = set(counts[counts >= settings.min_history_days].index)
    keep |= {settings.spy_ticker}
    keep |= set(SECTOR_ETFS.values())
    filtered = ohlcv[ohlcv["ticker"].isin(keep)].copy()
    dropped = set(universe_tickers) - keep
    if dropped:
        logger.info("Dropped %s tickers with short history (e.g. %s)", len(dropped), list(dropped)[:8])
    return filtered


def _download_fundamentals(universe: pd.DataFrame) -> pd.DataFrame:
    records = []

    def one(ticker: str, name: str, sector: str) -> dict:
        market_cap = None
        try:
            info = yf.Ticker(ticker).fast_info
            market_cap = getattr(info, "market_cap", None) or (info.get("marketCap") if isinstance(info, dict) else None)
            if market_cap is None and isinstance(info, dict):
                market_cap = info.get("market_cap")
        except Exception:
            logger.debug("fast_info failed for %s", ticker, exc_info=True)
        return {
            "ticker": ticker,
            "name": name,
            "sector": sector,
            "market_cap": float(market_cap) if market_cap else np.nan,
        }

    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = [
            pool.submit(one, row.ticker, row.name, row.sector)
            for row in universe.itertuples(index=False)
        ]
        for fut in as_completed(futures):
            records.append(fut.result())
    return pd.DataFrame(records)


def _download_earnings(tickers: list[str]) -> pd.DataFrame:
    records: list[dict] = []

    def one(ticker: str) -> list[dict]:
        out: list[dict] = []
        try:
            dates = yf.Ticker(ticker).get_earnings_dates(limit=24)
            if dates is None or dates.empty:
                return out
            idx = dates.index
            for stamp in pd.to_datetime(idx):
                out.append({"ticker": ticker, "earnings_date": stamp.tz_localize(None) if stamp.tzinfo else stamp})
        except Exception:
            logger.debug("earnings failed for %s", ticker, exc_info=True)
        return out

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(one, ticker) for ticker in tickers]
        for fut in as_completed(futures):
            records.extend(fut.result())
    if not records:
        return pd.DataFrame(columns=["ticker", "earnings_date"])
    df = pd.DataFrame(records).drop_duplicates()
    df["earnings_date"] = pd.to_datetime(df["earnings_date"]).dt.tz_localize(None)
    return df
