from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MP_",
        env_file=str(ROOT_DIR / ".env"),
        extra="ignore",
    )

    data_dir: Path = BACKEND_DIR / "data"
    start_date: str = "2018-01-01"
    spy_ticker: str = "SPY"
    universe_limit: int | None = None
    horizon_days: int = 5
    target_return: float = 0.05
    top_k: int = 10
    cost_bps: float = 5.0
    min_train_trading_days: int = 504
    walk_forward_step: int = 21
    min_history_days: int = 260
    random_seed: int = 42

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def features_dir(self) -> Path:
        return self.data_dir / "features"

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def predictions_dir(self) -> Path:
        return self.data_dir / "predictions"

    @property
    def backtest_dir(self) -> Path:
        return self.data_dir / "backtest"

    def ensure_dirs(self) -> None:
        for path in (
            self.raw_dir,
            self.features_dir,
            self.models_dir,
            self.predictions_dir,
            self.backtest_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
