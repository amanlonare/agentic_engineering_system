from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Project settings and environment variables.
    Uses Pydantic Settings for validation and .env support.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # LLM Settings
    OPENAI_API_KEY: str | None = None

    PRIMARY_MODEL_PROVIDER: str = "openai"
    OPENAI_MODEL_NAME: str = "gpt-4o-mini"

    # Infrastructure
    DATABASE_URL: str = "sqlite:///./engineering_agents.db"


settings = Settings()
