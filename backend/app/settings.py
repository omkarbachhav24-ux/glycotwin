from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration. Override with environment variables or .env."""

    # Postgres in Docker. Falls back to a local SQLite file so the backend
    # runs without a database server during development.
    database_url: str = f"sqlite:///{ROOT / 'backend' / 'glycotwin.db'}"
    data_dir: Path = ROOT / "data"
    artifact_path: Path = ROOT / "model_artifacts" / "glycotwin_models.joblib"
    metrics_path: Path = ROOT / "evaluation" / "metrics.json"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    default_stream_interval_seconds: float = 1.0

    class Config:
        env_file = ".env"
        env_prefix = "GLYCOTWIN_"

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
