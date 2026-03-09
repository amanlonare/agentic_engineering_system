from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Project settings and environment variables.
    Uses Pydantic Settings for validation and .env support.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # LLM Settings (Secrets only)
    OPENAI_API_KEY: str | None = None
    GITHUB_TOKEN: str | None = None
    # Ingestion Secrets
    GOOGLE_SERVICE_ACCOUNT_JSON_PATH: str | None = None
    SLACK_BOT_TOKEN: str | None = None

    APP_ENV: str = "dev"

    # Infrastructure (Defaults sourced from YAML config)
    DATABASE_URL: str = "sqlite:///./engineering_agents.db"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000


settings = Settings()
