from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    runner_image_python: str = "coderoyale-runner-python:latest"

    # Sandbox limits, applied to every throwaway container.
    sandbox_wall_timeout_seconds: int = 8
    sandbox_memory_mb: int = 256
    sandbox_cpus: float = 0.5
    sandbox_pids_limit: int = 64
    sandbox_tmpfs_mb: int = 32
    sandbox_output_limit_bytes: int = 64 * 1024

    # How many sandboxes may run at once on this host.
    max_concurrency: int = 4


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
