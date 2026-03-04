from pydantic import BaseModel, Field

from src.schemas.enums import GrowthRecommendationType


class GrowthRecommendation(BaseModel):
    """Structured output from the Growth Agent."""

    analysis: str = Field(
        description="Data-driven analysis justifying the recommendation"
    )
    recommendation_type: GrowthRecommendationType = Field(
        description="Signal to the supervisor for next routing step"
    )
    suggested_repo: str = Field(
        description="The repository that needs modification, if any"
    )
    drift_detected: bool = False
    false_positive_rate: float | None = None
    affected_segments: list[str] = []
    suggested_action: str | None = Field(
        default=None,
        description="Suggested corrective action based on the analysis, if any",
    )
