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
    ANTHROPIC_API_KEY: str | None = Field(default=None, repr=False)
    E2B_API_KEY: str | None = Field(default=None, repr=False)
    GITHUB_TOKEN: str | None = Field(default=None, repr=False)
    GITHUB_MCP_COMMAND: str = Field(
        default="npx -y @modelcontextprotocol/server-github", repr=True
    )
    GITHUB_REMOTE_MCP_URL: str = Field(
        default="https://api.githubcopilot.com/mcp/", repr=True
    )
    GITHUB_WEBHOOK_SECRET: str | None = Field(default=None, repr=False)

    # Google Drive Settings
    GOOGLE_DRIVE_MCP_COMMAND: str = Field(
        default="npx -y @modelcontextprotocol/server-gdrive", repr=True
    )
    GOOGLE_SERVICE_ACCOUNT_JSON_PATH: str | None = Field(
        default="secrets/google_service_account_cred.json", repr=False
    )
    SLACK_BOT_TOKEN: str | None = Field(default=None, repr=False)

    APP_ENV: str = "dev"

    # Infrastructure (Defaults sourced from YAML config)
    DATABASE_URL: str = "sqlite:///./engineering_agents.db"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # Storage Settings
    CHROMA_COLLECTION_NAME: str = "workspace_context"
    CHROMA_DB_PATH: str = "long_term_memory/vector"
    KUZU_DB_PATH: str = "long_term_memory/graph"

    # Ingestion Settings
    INGESTION_SOURCES_FILE: str = "ingestion_sources.yaml"

    # Resources & Workspace
    DYNAMIC_WORKSPACE_ENABLED: bool = Field(default=True, repr=True)
    # Mapping of repo/domain to MCP server name
    RESOURCE_MAPPINGS: dict[str, str] = Field(
        default={
            "github": "github",
            "gdrive": "gdrive",
            "google": "gdrive",
        },
        repr=True,
    )

    # Langfuse Settings
    LANGFUSE_PUBLIC_KEY: str | None = Field(default=None, repr=False)
    LANGFUSE_SECRET_KEY: str | None = Field(default=None, repr=False)
    LANGFUSE_BASE_URL: str = Field(default="https://cloud.langfuse.com", repr=True)

    # --- Storage: Evaluation (isolated, never mixes with production) ---
    EVAL_CHROMA_COLLECTION_NAME: str = "eval_rag_chunks"
    EVAL_CHROMA_DB_PATH: str = "evaluation/vector"
    EVAL_KUZU_DB_PATH: str = "evaluation/graph"


settings = Settings()
