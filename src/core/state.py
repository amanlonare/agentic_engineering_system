import operator
from typing import Annotated, List, Optional

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field

from src.schemas import (
    ApprovalStatus,
    NodeName,
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

    # Execution outcomes
    code_diffs: str = Field(default="")  # Tracked code changes
    validation_report: Optional[TestReport] = Field(
        default=None, description="Structured report of test runs"
    )

    # Human-in-the-loop state
    approval_status: ApprovalStatus = Field(
        default=ApprovalStatus.PENDING,
        description="State flag: pending, approved, rejected",
    )
