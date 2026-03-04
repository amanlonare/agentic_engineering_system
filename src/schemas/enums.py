from enum import Enum


class TriggerType(str, Enum):
    """Types of events that can trigger the workflow."""

    GITHUB_ISSUE = "github_issue"
    CLOUDWATCH_ALERT = "cloudwatch_alert"
    MANUAL = "manual"
    GROWTH_RECOMMENDATION = "growth_recommendation"


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


class GrowthRecommendationType(str, Enum):
    """Signals from Growth agent to determine next routing step."""

    REQUIRES_PLANNING = "requires_planning"
    REQUIRES_QUICK_FIX = "requires_quick_fix"
    NO_ACTION = "no_action"
