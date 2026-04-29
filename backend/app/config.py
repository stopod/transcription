from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="WHISPER_")

    data_dir: Path = Path("data")
    model_size: str = "large-v3"
    device: str = "cuda"
    compute_type: str = "float16"
    default_language: str | None = "ja"
    initial_prompt: str | None = None
    paragraph_gap_seconds: float = 2.0


settings = Settings()
(settings.data_dir / "jobs").mkdir(parents=True, exist_ok=True)

CORS_ORIGINS: list[str] = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
