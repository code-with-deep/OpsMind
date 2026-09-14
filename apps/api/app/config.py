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

    # LLM providers, tried in LLM_PROVIDER_ORDER; each takes part only when its key
    # is set (see opsmind.agents.llm). OpenAI reuses openai_api_key/openai_api_base
    # below; LLM_API_KEY / LLM_API_BASE / LLM_MODEL_* configure Groq.
    llm_provider_order: str = "gemini,openai,groq"
    gemini_api_key: str = ""
    gemini_api_base: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    gemini_model_fast: str = "gemini-2.5-flash"
    gemini_model_strong: str = "gemini-2.5-pro"
    openai_model_fast: str = "gpt-4.1-mini"
    openai_model_strong: str = "gpt-4.1"
    groq_api_key: str = ""
    llm_api_key: str = ""
    llm_api_base: str = "https://api.groq.com/openai/v1"
    llm_model_fast: str = "openai/gpt-oss-20b"
    llm_model_strong: str = "openai/gpt-oss-120b"

    max_critic_retries: int
    max_tool_calls_per_run: int

    # P5 — API auth (required for /investigations and /tools)
    opsmind_api_key: str

    # MT2 — web session JWT (email/password login)
    # P0-6: keeps a placeholder default so Settings() stays constructible in tests
    # and local dev without every test file setting JWT_SECRET — the actual
    # security enforcement (reject this placeholder / short secrets outside
    # dev/test) happens in main.py's _validate_secrets(), gated on APP_ENV.
    jwt_secret: str = "change-me-opsmind-jwt-secret-dev-only"
    jwt_expire_hours: int = 72
    auth_invite_default_max_uses: int = 10
    auth_invite_default_ttl_days: int = 14
    auth_max_active_invites: int = 25

    # Password reset / change (email link + Settings)
    auth_password_reset_ttl_minutes: int = 60
    auth_password_reset_max_per_hour: int = 5
    app_public_url: str = "http://localhost:3000"

    # P1-11: CORS allowed origins — comma-separated. Never "*" combined with
    # allow_credentials=True (invalid per spec, and permits credentialed
    # cross-origin requests from any page). Defaults to app_public_url.
    cors_allowed_origins: str = ""
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

    # P1-12 rate limits — configurable so a busy shared-IP office (or a test
    # suite exercising signup repeatedly) doesn't get needlessly locked out at
    # the default. Bug found by an actual full end-to-end test run: the
    # original hardcoded 5/hour signup limit broke 4 legitimate tests in a
    # single normal suite run — that's the same failure mode a real shared-NAT
    # office would hit under ordinary use, not just abuse.
    rate_limit_signup_per_hour: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
