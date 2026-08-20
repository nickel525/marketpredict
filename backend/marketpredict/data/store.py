from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from marketpredict.config import settings


class Store:
    """Parquet + JSON artifact store under backend/data."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root is not None else settings.data_dir
        settings.ensure_dirs()

    def path(self, *parts: str) -> Path:
        path = self.root.joinpath(*parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def write_parquet(self, df: pd.DataFrame, *parts: str) -> Path:
        path = self.path(*parts)
        df.to_parquet(path, index=False)
        return path

    def read_parquet(self, *parts: str) -> pd.DataFrame:
        path = self.path(*parts)
        if not path.exists():
            raise FileNotFoundError(f"Missing artifact: {path}")
        return pd.read_parquet(path)

    def exists(self, *parts: str) -> bool:
        return self.path(*parts).exists()

    def write_json(self, payload: Any, *parts: str) -> Path:
        path = self.path(*parts)
        path.write_text(json.dumps(payload, indent=2, default=_json_default))
        return path

    def read_json(self, *parts: str) -> Any:
        path = self.path(*parts)
        if not path.exists():
            raise FileNotFoundError(f"Missing artifact: {path}")
        return json.loads(path.read_text())


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return str(value)
