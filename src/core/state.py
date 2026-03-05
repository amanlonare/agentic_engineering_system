import operator
from typing import Annotated, List, Optional

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field

from src.schemas import (
    ApprovalStatus,
    GrowthRecommendation,
    NodeName,
    StepExecutionRecord,
    TechnicalPlan,
    TestReport,
    TriggerContext,
)


class EngineeringState(BaseModel):
    """
    The shared state passed horizontally between LangGraph nodes.
    Maintains the short-term context of a single execution thread.
    """

    # Agent conversational log (appends only)
    messages: Annotated[List[BaseMessage], operator.add] = Field(default_factory=list)

    # Context of the current trigger
    trigger: Optional[TriggerContext] = Field(
        default=None, description="Structured context of the triggering event"
    )

    # Workflow routing state
    next_action: NodeName = Field(
        default=NodeName.FINISH,
        description="The next node to route to (e.g., 'coder', 'ops')",
    )
    task_plan: Optional[TechnicalPlan] = Field(
        default=None, description="Structured plan from Planning node"
    )
    # Track completed steps from the plan
    completed_step_ids: Annotated[List[str], operator.add] = Field(
        default_factory=list,
        description="IDs of steps from the TechnicalPlan that are finished",
    )
    # Granular execution history
    execution_history: Annotated[List["StepExecutionRecord"], operator.add] = Field(
        default_factory=list, description="Structured log of each agent's actions"
    )
    growth_recommendations: List[GrowthRecommendation] = Field(
        default_factory=list,
        description="Recommendations from Growth agent (cleared after follow-up)",
    )
    accumulated_growth_notes: str = Field(
        default="",
        description="Persistent text of growth insights to be included in final PR description.",
    )
    follow_up_depth: int = Field(
        default=0,
        description="Number of follow-up plans created from growth recommendations (max 2)",
    )
    follow_up_context: Optional[str] = Field(
        default=None,
        description="When set, Planning Agent uses this as task description instead of the original user message",
    )
    verification_scripts: Annotated[List[str], operator.add] = Field(
        default_factory=list,
        description="Accumulated verification script paths (Coder -> Ops handoff)",
    )

    # Execution outcomes
    branch_name: str = Field(
        default="", description="The git branch name where changes were pushed"
    )
    code_diffs: str = Field(default="")  # Tracked code changes
    validation_report: Optional[TestReport] = Field(
        default=None, description="Structured report of test runs"
    )

    # Human-in-the-loop state
    approval_status: ApprovalStatus = Field(
        default=ApprovalStatus.PENDING,
        description="State flag: pending, approved, rejected",
    )

    # Error tracking
    error_message: Optional[str] = Field(
        default=None,
        description="If set, an agent has failed. Supervisor should FINISH.",
    )

    is_lightweight: bool = Field(
        default=False,
        description="If True, the task is simple and agents should use simplified prompts (e.g., no mocking).",
    )
