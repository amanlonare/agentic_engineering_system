from typing import List, Optional

from pydantic import BaseModel, Field


class TestCaseResult(BaseModel):
    """The outcome of a single test case."""

    name: str = Field(description="Name or ID of the test case")
    passed: bool = Field(description="Whether the test passed")
    error_message: Optional[str] = Field(
        default=None, description="Error or stacktrace if failed"
    )
    duration_ms: Optional[float] = Field(
        default=None, description="Execution time in ms"
    )


class TestReport(BaseModel):
    """Aggregated report of a test suite execution."""

    suite_name: str = Field(
        description="Name of the test suite (e.g., 'Integration Tests')"
    )
    total_tests: int = Field(description="Number of tests executed")
    passed_count: int = Field(description="Number of passing tests")
    failures: List[TestCaseResult] = Field(
        default_factory=list, description="Details of failing tests"
    )
    logs: Optional[str] = Field(
        default=None, description="Raw stdout/stderr logs from the test run"
    )

    @property
    def success(self) -> bool:
        return self.passed_count == self.total_tests
