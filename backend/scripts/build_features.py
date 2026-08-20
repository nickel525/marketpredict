#!/usr/bin/env python3
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from marketpredict.features.engineer import build_feature_frame

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> None:
    frame = build_feature_frame()
    print(f"Wrote {len(frame):,} feature rows for {frame['ticker'].nunique()} tickers")


if __name__ == "__main__":
    main()
