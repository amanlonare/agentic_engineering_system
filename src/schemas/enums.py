from enum import Enum


class TriggerType(str, Enum):
    """Types of events that can trigger the workflow."""

    GITHUB_ISSUE = "github_issue"
    CLOUDWATCH_ALERT = "cloudwatch_alert"
    MANUAL = "manual"


class NodeName(str, Enum):
    """Available worker nodes in the Engineering Graph."""

    SUPERVISOR = "supervisor"
    PLANNING = "planning"
    CODER = "coder"
    OPS = "ops"
    GROWTH = "growth"
    FINISH = "FINISH"


class ApprovalStatus(str, Enum):
    """Status flags for human-in-the-loop gates."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
