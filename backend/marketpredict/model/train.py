from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb
from xgboost import XGBClassifier

from marketpredict.config import settings
from marketpredict.data.store import Store
from marketpredict.features.engineer import FEATURE_COLUMNS

logger = logging.getLogger(__name__)


def train_walk_forward(store: Store | None = None) -> dict[str, Any]:
    """Train with expanding-window walk-forward validation. No random split."""
    store = store or Store()
    frame = store.read_parquet("features", "features.parquet")
    frame["date"] = pd.to_datetime(frame["date"]).dt.tz_localize(None)
    frame = frame.sort_values(["date", "ticker"]).reset_index(drop=True)

    labeled = frame.dropna(subset=["target"]).copy()
    labeled["target"] = labeled["target"].astype(int)
    dates = np.array(sorted(labeled["date"].unique()))
    min_len = settings.min_train_trading_days + settings.horizon_days + settings.walk_forward_step
    if len(dates) <= min_len:
        raise ValueError("Not enough history for walk-forward validation. Collect more data.")

    oos_parts: list[pd.DataFrame] = []
    fold = 0
    start_i = settings.min_train_trading_days
    while start_i < len(dates) - settings.horizon_days:
        train_last_idx = start_i - settings.horizon_days - 1
        if train_last_idx < settings.min_train_trading_days // 2:
            start_i += settings.walk_forward_step
            continue
        train_last_date = dates[train_last_idx]
        test_end_i = min(start_i + settings.walk_forward_step, len(dates) - settings.horizon_days)
        test_dates = dates[start_i:test_end_i]

        train_slice = labeled[labeled["date"] <= train_last_date]
        test_slice = labeled[labeled["date"].isin(test_dates)]
        if len(train_slice) < 2000 or test_slice.empty:
            start_i = test_end_i
            continue

        X_train, y_train = xy(train_slice)
        model = make_model(y_train)
        model.fit(X_train, y_train)
        proba = model.predict_proba(xy(test_slice)[0])[:, 1]
        out = test_slice[["date", "ticker", "close", "sector", "name", "fwd_return_5d", "target"]].copy()
        out["probability"] = proba
        out["fold"] = fold
        oos_parts.append(out)
        fold += 1
        logger.info(
            "Fold %s train_to=%s test=%s..%s train_rows=%s test_rows=%s",
            fold,
            pd.Timestamp(train_last_date).date(),
            pd.Timestamp(test_dates[0]).date(),
            pd.Timestamp(test_dates[-1]).date(),
            len(train_slice),
            len(test_slice),
        )
        start_i = test_end_i

    if not oos_parts:
        raise RuntimeError("Walk-forward produced no out-of-sample predictions.")

    oos = pd.concat(oos_parts, ignore_index=True)
    ranking_metrics = precision_at_k(oos)
    final_model, feature_importance = fit_final_model(labeled)

    latest_date = frame["date"].max()
    live = frame[frame["date"] == latest_date].reset_index(drop=True)
    live["probability"] = final_model.predict_proba(xy(live, allow_unlabeled=True)[0])[:, 1]
    contrib = contributions(final_model, live)

    store.write_parquet(oos, "predictions", "oos.parquet")
    live_cols = list(
        dict.fromkeys(
            [
                "date",
                "ticker",
                "name",
                "sector",
                "close",
                "volume",
                "probability",
                *FEATURE_COLUMNS,
            ]
        )
    )
    store.write_parquet(live[[c for c in live_cols if c in live.columns]], "predictions", "latest.parquet")
    store.write_parquet(contrib, "predictions", "latest_contributions.parquet")
    final_model.save_model(str(store.path("models", "xgb_model.json")))
    store.write_json(
        {
            "feature_columns": FEATURE_COLUMNS,
            "importance": feature_importance,
            "ranking_metrics": ranking_metrics,
            "n_oos_rows": int(len(oos)),
            "n_folds": int(oos["fold"].nunique()),
            "positive_rate": float(labeled["target"].mean()),
            "latest_date": str(pd.Timestamp(latest_date).date()),
        },
        "models",
        "meta.json",
    )
    logger.info("Walk-forward complete: %s OOS rows, metrics=%s", len(oos), ranking_metrics)
    return {
        "ranking_metrics": ranking_metrics,
        "n_oos_rows": int(len(oos)),
        "n_folds": int(oos["fold"].nunique()),
        "latest_date": str(pd.Timestamp(latest_date).date()),
    }


def xy(df: pd.DataFrame, allow_unlabeled: bool = False) -> tuple[pd.DataFrame, np.ndarray | None]:
    X = pd.DataFrame({col: df[col] if col in df.columns else np.nan for col in FEATURE_COLUMNS})
    if allow_unlabeled:
        return X, None
    return X, df["target"].to_numpy()


def make_model(y: np.ndarray) -> XGBClassifier:
    pos = max(int((y == 1).sum()), 1)
    neg = max(int((y == 0).sum()), 1)
    return XGBClassifier(
        n_estimators=250,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=25,
        reg_lambda=1.5,
        objective="binary:logistic",
        eval_metric="logloss",
        tree_method="hist",
        n_jobs=-1,
        random_state=settings.random_seed,
        scale_pos_weight=neg / pos,
        missing=np.nan,
    )


def fit_final_model(labeled: pd.DataFrame) -> tuple[XGBClassifier, dict[str, float]]:
    X, y = xy(labeled)
    model = make_model(y)
    model.fit(X, y)
    importance = {
        name: float(score)
        for name, score in sorted(
            zip(FEATURE_COLUMNS, model.feature_importances_),
            key=lambda item: item[1],
            reverse=True,
        )
    }
    return model, importance


def contributions(model: XGBClassifier, live: pd.DataFrame) -> pd.DataFrame:
    booster = model.get_booster()
    X = xy(live, allow_unlabeled=True)[0]
    contrib = booster.predict(xgb.DMatrix(X, feature_names=FEATURE_COLUMNS), pred_contribs=True)
    cols = FEATURE_COLUMNS + ["bias"]
    out = pd.DataFrame(contrib, columns=cols)
    out.insert(0, "ticker", live["ticker"].to_numpy())
    out.insert(1, "date", pd.to_datetime(live["date"]).to_numpy())
    return out


def precision_at_k(oos: pd.DataFrame, ks: tuple[int, ...] = (5, 10, 20)) -> dict[str, float]:
    rows = []
    for _, grp in oos.groupby("date"):
        ranked = grp.sort_values("probability", ascending=False)
        for k in ks:
            top = ranked.head(k)
            if len(top) < k:
                continue
            rows.append({"k": k, "precision": float(top["target"].mean())})
    metrics = pd.DataFrame(rows)
    result: dict[str, float] = {}
    for k in ks:
        subset = metrics[metrics["k"] == k]["precision"] if not metrics.empty else pd.Series(dtype=float)
        result[f"precision_at_{k}"] = float(subset.mean()) if len(subset) else float("nan")
    return result
