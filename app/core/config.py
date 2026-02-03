from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = "Smart Paper Service"
    environment: str = "local"
    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://localhost:3000",
    )


settings = Settings()
