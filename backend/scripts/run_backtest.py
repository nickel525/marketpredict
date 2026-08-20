#!/usr/bin/env python3
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from marketpredict.backtest.engine import run_backtest

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> None:
    result = run_backtest()
    summary = {
        "config": result["config"],
        "model": result["model"],
        "strategy": result["strategy"],
        "strategy_net": result["strategy_net"],
        "spy": result["spy"],
        "random": result["random"],
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
