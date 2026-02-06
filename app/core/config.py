import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_STORAGE_DIR = PROJECT_ROOT / "storage"
DEFAULT_DATABASE_URL = f"sqlite:///{(DEFAULT_STORAGE_DIR / 'smart_paper.db').as_posix()}"


@dataclass(frozen=True)
class Settings:
    app_name: str = "Smart Paper Service"
    environment: str = "local"
    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://localhost:3000",
    )

    # Database configuration
    database_url: str = os.getenv(
        "DATABASE_URL",
        DEFAULT_DATABASE_URL,
    )

    # Storage configuration
    storage_base_dir: str = os.getenv(
        "STORAGE_BASE_DIR",
        str(DEFAULT_STORAGE_DIR),
    )
    storage_base_url: str = os.getenv(
        "STORAGE_BASE_URL",
        "http://localhost:8000/static"
    )


settings = Settings()
