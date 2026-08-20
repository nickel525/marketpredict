from __future__ import annotations

import io
import logging

import pandas as pd
import requests

from marketpredict.config import settings
from marketpredict.data.store import Store

logger = logging.getLogger(__name__)

WIKI_SP500 = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
WIKI_NASDAQ100 = "https://en.wikipedia.org/wiki/Nasdaq-100"
WIKI_HEADERS = {
    "User-Agent": "MarketPredict/1.0 (educational research; https://github.com/marketpredict)"
}


def _read_html(url: str) -> list[pd.DataFrame]:
    response = requests.get(url, headers=WIKI_HEADERS, timeout=30)
    response.raise_for_status()
    return pd.read_html(io.StringIO(response.text), flavor="lxml")

FALLBACK_UNIVERSE = [
    ("AAPL", "Apple", "Information Technology"),
    ("MSFT", "Microsoft", "Information Technology"),
    ("NVDA", "NVIDIA", "Information Technology"),
    ("AMZN", "Amazon", "Consumer Discretionary"),
    ("GOOGL", "Alphabet", "Communication Services"),
    ("META", "Meta Platforms", "Communication Services"),
    ("BRK-B", "Berkshire Hathaway", "Financials"),
    ("JPM", "JPMorgan Chase", "Financials"),
    ("XOM", "Exxon Mobil", "Energy"),
    ("UNH", "UnitedHealth", "Health Care"),
    ("JNJ", "Johnson & Johnson", "Health Care"),
    ("V", "Visa", "Financials"),
    ("PG", "Procter & Gamble", "Consumer Staples"),
    ("MA", "Mastercard", "Financials"),
    ("HD", "Home Depot", "Consumer Discretionary"),
    ("COST", "Costco", "Consumer Staples"),
    ("ABBV", "AbbVie", "Health Care"),
    ("CVX", "Chevron", "Energy"),
    ("MRK", "Merck", "Health Care"),
    ("PEP", "PepsiCo", "Consumer Staples"),
    ("KO", "Coca-Cola", "Consumer Staples"),
    ("AVGO", "Broadcom", "Information Technology"),
    ("WMT", "Walmart", "Consumer Staples"),
    ("LLY", "Eli Lilly", "Health Care"),
    ("BAC", "Bank of America", "Financials"),
    ("ADBE", "Adobe", "Information Technology"),
    ("CRM", "Salesforce", "Information Technology"),
    ("NFLX", "Netflix", "Communication Services"),
    ("AMD", "Advanced Micro Devices", "Information Technology"),
    ("ORCL", "Oracle", "Information Technology"),
    ("CSCO", "Cisco", "Information Technology"),
    ("ACN", "Accenture", "Information Technology"),
    ("MCD", "McDonald's", "Consumer Discretionary"),
    ("DIS", "Disney", "Communication Services"),
    ("TMO", "Thermo Fisher", "Health Care"),
    ("ABT", "Abbott", "Health Care"),
    ("CAT", "Caterpillar", "Industrials"),
    ("GE", "GE Aerospace", "Industrials"),
    ("IBM", "IBM", "Information Technology"),
    ("NOW", "ServiceNow", "Information Technology"),
    ("INTU", "Intuit", "Information Technology"),
    ("AMAT", "Applied Materials", "Information Technology"),
    ("TXN", "Texas Instruments", "Information Technology"),
    ("QCOM", "Qualcomm", "Information Technology"),
    ("AMGN", "Amgen", "Health Care"),
    ("ISRG", "Intuitive Surgical", "Health Care"),
    ("PFE", "Pfizer", "Health Care"),
    ("PM", "Philip Morris", "Consumer Staples"),
    ("NEE", "NextEra Energy", "Utilities"),
    ("RTX", "RTX", "Industrials"),
    ("HON", "Honeywell", "Industrials"),
    ("UNP", "Union Pacific", "Industrials"),
    ("BA", "Boeing", "Industrials"),
    ("SPG", "Simon Property", "Real Estate"),
    ("PLD", "Prologis", "Real Estate"),
    ("LIN", "Linde", "Materials"),
    ("SHW", "Sherwin-Williams", "Materials"),
    ("NKE", "Nike", "Consumer Discretionary"),
    ("SBUX", "Starbucks", "Consumer Discretionary"),
    ("LOW", "Lowe's", "Consumer Discretionary"),
    ("GS", "Goldman Sachs", "Financials"),
    ("MS", "Morgan Stanley", "Financials"),
    ("BLK", "BlackRock", "Financials"),
    ("C", "Citigroup", "Financials"),
    ("WFC", "Wells Fargo", "Financials"),
    ("COP", "ConocoPhillips", "Energy"),
    ("SLB", "Schlumberger", "Energy"),
    ("T", "AT&T", "Communication Services"),
    ("VZ", "Verizon", "Communication Services"),
    ("CMCSA", "Comcast", "Communication Services"),
    ("TMUS", "T-Mobile", "Communication Services"),
    ("GILD", "Gilead", "Health Care"),
    ("MDT", "Medtronic", "Health Care"),
    ("DHR", "Danaher", "Health Care"),
    ("SYK", "Stryker", "Health Care"),
    ("DE", "Deere", "Industrials"),
    ("LMT", "Lockheed Martin", "Industrials"),
    ("UPS", "UPS", "Industrials"),
    ("SO", "Southern Company", "Utilities"),
    ("DUK", "Duke Energy", "Utilities"),
    ("AMT", "American Tower", "Real Estate"),
    ("EQIX", "Equinix", "Real Estate"),
    ("APD", "Air Products", "Materials"),
    ("FCX", "Freeport-McMoRan", "Materials"),
    ("MO", "Altria", "Consumer Staples"),
    ("MDLZ", "Mondelez", "Consumer Staples"),
    ("TJX", "TJX", "Consumer Discretionary"),
    ("BKNG", "Booking", "Consumer Discretionary"),
    ("TSLA", "Tesla", "Consumer Discretionary"),
    ("INTC", "Intel", "Information Technology"),
    ("MU", "Micron", "Information Technology"),
    ("LRCX", "Lam Research", "Information Technology"),
    ("KLAC", "KLA", "Information Technology"),
    ("ADI", "Analog Devices", "Information Technology"),
    ("PANW", "Palo Alto Networks", "Information Technology"),
    ("CRWD", "CrowdStrike", "Information Technology"),
    ("SNPS", "Synopsys", "Information Technology"),
    ("CDNS", "Cadence", "Information Technology"),
    ("REGN", "Regeneron", "Health Care"),
    ("VRTX", "Vertex", "Health Care"),
]


def _normalize_ticker(symbol: str) -> str:
    return str(symbol).strip().replace(".", "-")


def _read_sp500() -> pd.DataFrame:
    tables = _read_html(WIKI_SP500)
    raw = tables[0]
    df = pd.DataFrame(
        {
            "ticker": raw["Symbol"].map(_normalize_ticker),
            "name": raw["Security"].astype(str),
            "sector": raw["GICS Sector"].astype(str),
            "industry": raw.get("GICS Sub-Industry", pd.Series("", index=raw.index)).astype(str),
        }
    )
    df["source"] = "sp500"
    return df


def _read_nasdaq100() -> pd.DataFrame:
    tables = _read_html(WIKI_NASDAQ100)
    raw = None
    for table in tables:
        columns = {str(c).lower() for c in table.columns}
        if "ticker" in columns or "symbol" in columns:
            raw = table
            break
    if raw is None:
        return pd.DataFrame(columns=["ticker", "name", "sector", "industry", "source"])

    rename = {}
    for col in raw.columns:
        key = str(col).lower()
        if key in {"ticker", "symbol"}:
            rename[col] = "ticker"
        elif key in {"company", "company name", "security"}:
            rename[col] = "name"
        elif "gics" in key and "sector" in key or key == "sector":
            rename[col] = "sector"
        elif "industry" in key:
            rename[col] = "industry"
    raw = raw.rename(columns=rename)
    if "ticker" not in raw.columns:
        return pd.DataFrame(columns=["ticker", "name", "sector", "industry", "source"])

    df = pd.DataFrame(
        {
            "ticker": raw["ticker"].map(_normalize_ticker),
            "name": raw["name"].astype(str) if "name" in raw.columns else raw["ticker"].astype(str),
            "sector": raw["sector"].astype(str) if "sector" in raw.columns else "Unknown",
            "industry": raw["industry"].astype(str) if "industry" in raw.columns else "",
        }
    )
    df["source"] = "nasdaq100"
    return df


def _fallback_universe() -> pd.DataFrame:
    df = pd.DataFrame(FALLBACK_UNIVERSE, columns=["ticker", "name", "sector"])
    df["industry"] = ""
    df["source"] = "fallback"
    return df


def load_universe(limit: int | None = None, refresh: bool = False) -> pd.DataFrame:
    """Load ~500–600 liquid U.S. names (S&P 500 plus extra Nasdaq-100)."""
    store = Store()
    cache_path = ("raw", "universe.parquet")
    limit = settings.universe_limit if limit is None else limit

    if not refresh and store.exists(*cache_path):
        universe = store.read_parquet(*cache_path)
        logger.info("Loaded cached universe: %s tickers", len(universe))
        return _apply_limit(universe, limit)

    frames = []
    try:
        frames.append(_read_sp500())
        logger.info("Fetched S&P 500 constituents")
    except Exception:
        logger.exception("Failed to fetch S&P 500 list")
    try:
        extra = _read_nasdaq100()
        if extra.empty:
            logger.info("Nasdaq-100 constituents table not found; using S&P 500")
        else:
            frames.append(extra)
            logger.info("Fetched Nasdaq-100 constituents")
    except Exception:
        logger.exception("Failed to fetch Nasdaq-100 list")

    if frames:
        universe = pd.concat(frames, ignore_index=True)
        universe = universe.drop_duplicates(subset=["ticker"]).sort_values("ticker")
        universe = universe[universe["ticker"].str.len().between(1, 6)].reset_index(drop=True)
        logger.info("Fetched live universe: %s tickers", len(universe))
    else:
        logger.warning("Using fallback universe")
        universe = _fallback_universe()

    store.write_parquet(universe, *cache_path)
    return _apply_limit(universe, limit)


def _apply_limit(universe: pd.DataFrame, limit: int | None) -> pd.DataFrame:
    if limit is None:
        return universe.reset_index(drop=True)
    return universe.head(int(limit)).reset_index(drop=True)
