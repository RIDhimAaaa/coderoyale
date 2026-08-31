from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # infra
    database_url: str = "postgresql+asyncpg://coderoyale:coderoyale@localhost:5432/coderoyale"
    redis_url: str = "redis://localhost:6379/0"
    executor_url: str = "http://localhost:8001"

    # auth
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720

    # game
    match_duration_seconds: int = 600
    elo_k_factor: int = 32

    # matchmaking
    matchmaker_poll_seconds: float = 0.5


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
