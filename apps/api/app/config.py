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

    # MT2 — web session JWT (email/password login)
    jwt_secret: str = "change-me-opsmind-jwt-secret-dev-only"
    jwt_expire_hours: int = 72
    auth_invite_default_max_uses: int = 10
    auth_invite_default_ttl_days: int = 14
    auth_max_active_invites: int = 25

    # Password reset / change (email link + Settings)
    auth_password_reset_ttl_minutes: int = 60
    auth_password_reset_max_per_hour: int = 5
    app_public_url: str = "http://localhost:3000"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    email_from: str = "OpsMind <noreply@opsmind.local>"

    # MT3 — playbooks / embeddings
    opsmind_embedding_provider: str = "local"
    openai_api_key: str = ""
    openai_api_base: str = "https://api.openai.com/v1"
    opsmind_embedding_model: str = "text-embedding-3-small"
    playbook_max_count: int = 25
    playbook_max_upload_mb: int = 2

    # MT4 — CSV soft limits
    csv_max_upload_mb: int = 10
    csv_max_rows: int = 50000


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
