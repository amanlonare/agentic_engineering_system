from pydantic import BaseModel, ConfigDict, Field


class RouteDecision(BaseModel):
    """The decision output by the Supervisor to route the graph."""

    model_config = ConfigDict(extra="ignore")

    next_node: str = Field(
        description="The exact name of the next node to route to. MUST be one of: 'planning', 'coder', 'ops', 'growth', or 'FINISH'"
    )
    reasoning: str = Field(
        description="A concise explanation of why this routing decision was made."
    )
