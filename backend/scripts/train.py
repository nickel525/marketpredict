#!/usr/bin/env python3
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from marketpredict.model.train import train_walk_forward

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> None:
    result = train_walk_forward()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
