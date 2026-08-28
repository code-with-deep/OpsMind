from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration — all values come from environment / .env only."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str
    app_name: str
    log_level: str
    api_host: str
    api_port: int

    database_url: str
    database_url_sync: str
    database_url_readonly: str

    llm_api_key: str
    llm_api_base: str
    llm_model_fast: str
    llm_model_strong: str

    max_critic_retries: int
    max_tool_calls_per_run: int

    # P5 — API auth (required for /investigations and /tools)
    opsmind_api_key: str


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
