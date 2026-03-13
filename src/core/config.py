from pydantic import Field
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
    OPENAI_API_KEY: str | None = Field(default=None, repr=False)
    GITHUB_TOKEN: str | None = Field(default=None, repr=False)
    GITHUB_WEBHOOK_SECRET: str | None = Field(default=None, repr=False)

    # Ingestion Secrets
    GOOGLE_SERVICE_ACCOUNT_JSON_PATH: str | None = Field(default=None, repr=False)
    SLACK_BOT_TOKEN: str | None = Field(default=None, repr=False)

    APP_ENV: str = "dev"

    # Infrastructure (Defaults sourced from YAML config)
    DATABASE_URL: str = "sqlite:///./engineering_agents.db"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # --- Storage: Production ---
    CHROMA_COLLECTION_NAME: str = "rag_chunks"
    CHROMA_DB_PATH: str = "long_term_memory/vector"
    KUZU_DB_PATH: str = "long_term_memory/graph"

    # --- Storage: Evaluation (isolated, never mixes with production) ---
    EVAL_CHROMA_COLLECTION_NAME: str = "eval_rag_chunks"
    EVAL_CHROMA_DB_PATH: str = "evaluation/vector"
    EVAL_KUZU_DB_PATH: str = "evaluation/graph"


settings = Settings()
