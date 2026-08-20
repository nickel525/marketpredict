from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from xgboost import XGBClassifier

from marketpredict.data.store import Store
from marketpredict.features.engineer import FEATURE_COLUMNS
from marketpredict.model.train import contributions, xy


def load_model(store: Store | None = None) -> XGBClassifier:
    store = store or Store()
    path = store.path("models", "xgb_model.json")
    if not path.exists():
        raise FileNotFoundError(f"Trained model not found at {path}. Run scripts/train.py first.")
    model = XGBClassifier()
    model.load_model(str(path))
    return model


def predict_frame(df: pd.DataFrame, model: XGBClassifier | None = None) -> pd.DataFrame:
    model = model or load_model()
    out = df.copy().reset_index(drop=True)
    out["probability"] = model.predict_proba(xy(out, allow_unlabeled=True)[0])[:, 1]
    return out


def score_latest(store: Store | None = None) -> dict[str, str | int]:
    """Score the newest feature date with the saved model. Does not retrain."""
    store = store or Store()
    frame = store.read_parquet("features", "features.parquet")
    frame["date"] = pd.to_datetime(frame["date"]).dt.tz_localize(None)
    latest_date = frame["date"].max()
    live = frame[frame["date"] == latest_date].reset_index(drop=True)
    if live.empty:
        raise RuntimeError("Feature table is empty; run build_features.py first.")
    model = load_model(store)
    live = predict_frame(live, model)
    contrib = contributions(model, live)
    live_cols = list(
        dict.fromkeys(
            ["date", "ticker", "name", "sector", "close", "volume", "probability", *FEATURE_COLUMNS]
        )
    )
    store.write_parquet(live[[c for c in live_cols if c in live.columns]], "predictions", "latest.parquet")
    store.write_parquet(contrib, "predictions", "latest_contributions.parquet")
    meta = store.read_json("models", "meta.json") if store.exists("models", "meta.json") else {}
    meta["latest_date"] = str(pd.Timestamp(latest_date).date())
    meta["scored_at"] = datetime.now(timezone.utc).isoformat()
    store.write_json(meta, "models", "meta.json")
    return {
        "latest_date": str(pd.Timestamp(latest_date).date()),
        "n_scored": int(len(live)),
    }


def model_path(store: Store | None = None) -> Path:
    store = store or Store()
    return store.path("models", "xgb_model.json")


def feature_contributions(df: pd.DataFrame, model: XGBClassifier | None = None) -> pd.DataFrame:
    model = model or load_model()
    return contributions(model, df.reset_index(drop=True))
