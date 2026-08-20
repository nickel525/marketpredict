#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from marketpredict.data.collector import collect_market_data, generate_synthetic_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect OHLCV, fundamentals, and earnings.")
    parser.add_argument("--limit", type=int, default=None, help="Cap the universe size for a faster run.")
    parser.add_argument("--start", type=str, default=None, help="Start date YYYY-MM-DD.")
    parser.add_argument("--refresh-universe", action="store_true", help="Re-download the ticker list.")
    parser.add_argument("--synthetic", action="store_true", help="Generate synthetic data instead of Yahoo Finance.")
    args = parser.parse_args()
    if args.synthetic:
        paths = generate_synthetic_data()
    else:
        paths = collect_market_data(limit=args.limit, start=args.start, refresh_universe=args.refresh_universe)
    print(paths)


if __name__ == "__main__":
    main()
