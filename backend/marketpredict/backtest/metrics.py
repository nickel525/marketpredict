from __future__ import annotations

import numpy as np
import pandas as pd


def performance_metrics(
    returns: pd.Series,
    equity: pd.Series,
    periods_per_year: float = 52.0,
    hit_threshold: float = 0.0,
) -> dict[str, float]:
    returns = pd.Series(returns).dropna()
    equity = pd.Series(equity).dropna()
    if returns.empty or equity.empty:
        return {
            "cagr": float("nan"),
            "sharpe": float("nan"),
            "max_drawdown": float("nan"),
            "hit_rate": float("nan"),
            "avg_weekly_return": float("nan"),
            "pct_weeks_ge_5pct": float("nan"),
        }

    start = float(equity.iloc[0])
    end = float(equity.iloc[-1])
    n_periods = max(len(returns), 1)
    years = n_periods / periods_per_year
    cagr = (end / start) ** (1 / years) - 1 if start > 0 and years > 0 else float("nan")
    vol = float(returns.std(ddof=1)) if len(returns) > 1 else float("nan")
    sharpe = float(returns.mean() / vol * np.sqrt(periods_per_year)) if vol and vol > 0 else float("nan")
    peak = equity.cummax()
    drawdown = equity / peak - 1
    return {
        "cagr": float(cagr),
        "sharpe": float(sharpe),
        "max_drawdown": float(drawdown.min()),
        "hit_rate": float((returns > hit_threshold).mean()),
        "avg_weekly_return": float(returns.mean()),
        "pct_weeks_ge_5pct": float((returns >= 0.05).mean()),
    }
