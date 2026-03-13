from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    GITHUB_REPO = "github_repo"
    GOOGLE_DOC = "google_doc"
    GOOGLE_SHEET = "google_sheet"
    SLACK_CONVERSATION = "slack_conversation"
    PDF_FILE = "pdf_file"
    LOCAL_DIR = "local_dir"
    UNSUPPORTED = "unsupported"


class IdentifiedSource(BaseModel):
    """Represents a categorized data source ready for chunking."""

    source_type: SourceType
    identifier: str  # URL, Local Path, or Slack ID
    metadata: Dict[str, Any] = Field(default_factory=dict)
    is_verified: bool = False


class ConnectorConfig(BaseModel):
    """Configuration for a specific data source connector."""

    enabled: bool = False
    timeout: int = 30
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IngestionConfig(BaseModel):
    """Global configuration for the ingestion system."""

    connectors: Dict[str, ConnectorConfig] = Field(default_factory=dict)
