from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class GitHubIssuePayload(BaseModel):
    """Schema for GitHub issue triggers."""

    repository: str = Field(description="Full name of the repo (e.g., owner/repo)")
    issue_number: int = Field(description="The GitHub issue number")
    title: str = Field(description="Title of the issue")
    body: Optional[str] = Field(default=None, description="Markdown body of the issue")
    labels: list[str] = Field(default_factory=list, description="List of issue labels")
    action: str = Field(default="opened", description="Action performed: opened, labeled, etc.")
    sender: str = Field(default="", description="GitHub username of the person who triggered the event")


class CloudWatchPayload(BaseModel):
    """Schema for CloudWatch alert triggers."""

    alarm_name: str = Field(description="Name of the CloudWatch alarm")
    state: str = Field(description="Current state: ALARM, OK, INSUFFICIENT_DATA")
    reason: str = Field(description="Reason for the state change")
    timestamp: str = Field(description="ISO timestamp of the event")


class TriggerContext(BaseModel):
    """Union-like container for various trigger types."""

    type: str  # Use TriggerType enum values
    payload: Dict[str, Any]  # Raw payload for fallback or extensibility
    repo_name: Optional[str] = Field(
        default=None, description="The identified repository name from WorkspaceManager"
    )
    structured_payload: Optional[BaseModel] = Field(
        default=None, description="The parsed Pydantic model for the trigger"
    )
