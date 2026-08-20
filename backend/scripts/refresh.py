#!/usr/bin/env python3
"""Refresh Yahoo prices and rescore the dashboard without a full walk-forward retrain."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from marketpredict.data.collector import collect_market_data, refresh_market_data
from marketpredict.features.engineer import build_feature_frame
from marketpredict.model.predict import score_latest
from marketpredict.model.train import train_walk_forward

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download the latest daily bars, rebuild features, and update rankings."
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Re-download the entire history from MP_START_DATE instead of the last ~10 days.",
    )
    parser.add_argument("--refresh-universe", action="store_true", help="Re-fetch the S&P 500 membership list.")
    parser.add_argument("--earnings", action="store_true", help="Also refresh earnings dates (slower).")
    parser.add_argument(
        "--retrain",
        action="store_true",
        help="Re-run walk-forward training after the refresh. Weekly is enough; daily scoring uses the saved model.",
    )
    args = parser.parse_args()

    if args.full:
        collect = collect_market_data(refresh_universe=args.refresh_universe)
    else:
        collect = refresh_market_data(
            refresh_universe=args.refresh_universe,
            refresh_earnings=args.earnings,
        )
    frame = build_feature_frame()
    if args.retrain:
        scored = train_walk_forward()
    else:
        scored = score_latest()
    result = {
        "collect": collect,
        "n_feature_rows": int(len(frame)),
        "score": scored,
    }
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
