# MarketPredict

Full-stack app that ranks liquid U.S. stocks by:

`P(return over the next 5 trading days >= 5%)`

The model is an XGBoost classifier trained with **walk-forward validation** (no random train/test split). Features on date `T` use only information available at or before `T`.

## Architecture

| Module | Path | Role |
| --- | --- | --- |
| Data collection | `backend/marketpredict/data/` | Universe, Yahoo Finance OHLCV / sector / market cap / earnings |
| Feature engineering | `backend/marketpredict/features/` | Returns, momentum, volume, volatility, RSI, MAs, 52-week high, gaps, vs S&P 500, vs sector |
| Model | `backend/marketpredict/model/` | Walk-forward XGBoost + latest rankings |
| Backtest | `backend/marketpredict/backtest/` | Weekly top-10 equal-weight vs S&P 500 and random |
| API | `backend/api/` | FastAPI |
| Frontend | `frontend/` | React + TypeScript + Tailwind |

Artifacts are written to `backend/data/` (gitignored).

## Requirements

- Python 3.11+
- Node.js 20+
- Internet access for Yahoo Finance and Wikipedia (ticker universe)

The universe is the current S&P 500 (about 500 liquid U.S. names). Wikipedia is fetched with a browser User-Agent; pandas' default scraper is often blocked with HTTP 403.

## Install

```bash
cd /path/to/marketpredict

python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

cd frontend
npm install
cd ..
```

## Run the pipeline

Commands below assume the virtualenv is active and you are in the repo root.

### 1. Collect market data

Full liquid universe (S&P 500 plus extra Nasdaq-100 names, typically ~500–600 stocks):

```bash
cd backend
python scripts/collect_data.py --refresh-universe
```

Faster smoke run (first N names after the universe is built):

```bash
python scripts/collect_data.py --limit 80 --start 2018-01-01
```

This writes:

- `data/raw/ohlcv.parquet`
- `data/raw/universe.parquet`
- `data/raw/fundamentals.parquet` (latest market cap, sector)
- `data/raw/earnings.parquet`

The first full download can take 10–20 minutes. Subsequent feature/train steps read the parquet files and do not re-download.

### Keep prices and rankings current

The dashboard **does not** fetch live quotes on each page load. It reads the last snapshot under `backend/data/`. Yahoo daily bars also settle after the US close, so “most up to date” for this model means **the latest daily bar Yahoo has published**, not a millisecond tick.

After the cash session (about **4:15–8:00 PM ET**, when Yahoo’s daily close is usually stable), run:

```bash
cd backend
source ../.venv/bin/activate
python scripts/refresh.py
```

That command:

1. Re-downloads the last ~10 days of OHLCV (not the full 2018 history) and overwrites overlapping rows
2. Rebuilds features through the newest bar
3. Re-scores every name with the **saved** XGBoost model
4. Updates `data/predictions/latest.parquet`

Then reload [http://localhost:5173](http://localhost:5173). The rankings header shows the price date and when Yahoo was last pulled. You do not need to restart the API.

| When | Command | Why |
| --- | --- | --- |
| Every trading day after the close | `python scripts/refresh.py` | New prices + new ranking |
| During market hours | same command | Last bar is today’s **in-progress** daily candle (Yahoo is typically delayed ~15 minutes) |
| Weekly | `python scripts/refresh.py --retrain` | Refit the model on new labeled weeks |
| Membership changes | `python scripts/refresh.py --refresh-universe` | New S&P 500 constituents |
| Split/data suspicion | `python scripts/refresh.py --full` | Rebuild the entire price history |

Weekends and holidays: Yahoo’s latest bar is the previous session’s close; running refresh then just confirms you already have it.

Offline demo data (no Yahoo Finance):

```bash
python scripts/collect_data.py --synthetic
```

### 2. Build features

```bash
python scripts/build_features.py
```

Target: `1` if `close[T+5] / close[T] - 1 >= 0.05`, else `0`.

### 3. Train (walk-forward)

```bash
python scripts/train.py
```

The trainer:

- Fits an expanding-window XGBoost model
- Embargoes 5 trading days so labels that need future prices never enter the training set for a given fold
- Saves out-of-sample probabilities to `data/predictions/oos.parquet`
- Fits a final model on all labeled rows and scores the latest date for the dashboard

### 4. Backtest

```bash
python scripts/run_backtest.py
```

Strategy: every week, buy the model’s **top 10** names, equal weight, hold **5 trading days**. Costs default to **5 bps per side** on traded notional (`MP_COST_BPS`).

Reported metrics:

- Precision@5 / @10 / @20 (from walk-forward rankings)
- Hit rate (share of weeks with positive portfolio return)
- Share of weeks returning 5%+
- Average weekly return
- CAGR, Sharpe (weekly, rf = 0), max drawdown
- Same metrics after costs
- S&P 500 buy-and-hold
- Random 10-stock equal-weight benchmark

## Launch the app

Terminal 1 — API:

```bash
cd backend
source ../.venv/bin/activate
uvicorn api.main:app --reload --port 8000
```

Terminal 2 — UI:

```bash
cd frontend
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

- Rankings table: **Stocks Most Likely to Gain 5% This Week**
- Click a row for price history, probability, feature contributions, and a short explanation
- **Backtest** page: equity curve vs S&P 500 plus CAGR / Sharpe / drawdown / hit rate

## Configuration

Environment variables use the `MP_` prefix (see `.env.example`):

| Variable | Default | Meaning |
| --- | --- | --- |
| `MP_START_DATE` | `2018-01-01` | OHLCV start |
| `MP_UNIVERSE_LIMIT` | unset | Cap universe size |
| `MP_COST_BPS` | `5` | Transaction cost per side |
| `MP_TOP_K` | `10` | Holdings per week |
| `MP_DATA_DIR` | `backend/data` | Artifact root |

## Tests

```bash
cd backend
python -m pytest tests -q
```

`tests/test_features_leakage.py` checks that mutating prices after date `T` does not change features at `T`, and that the 5-day target *does* change.

## Notes

- Latest market cap is used for display only, not as a model feature (it is not point-in-time). Liquidity in the model is `log(close * volume)`.
- Predicted probabilities are useful for **ranking**. They are not strictly calibrated (an 80% score is not a claim that 8/10 names will hit +5%).
- The live universe is today’s S&P 500 membership, so the historical backtest has survivorship bias.
- This is a research prototype, not investment advice.
