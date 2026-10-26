"""Agent loop contracts per Batch X10."""

from typing import Literal

from pydantic import Field

from backend.app.contracts.common import StrictContractModel

StepStatus = Literal["success", "denied", "error"]


class AgentStep(StrictContractModel):
    """Single execution step in an agent tool loop per Batch X10."""

    step_number: int = Field(ge=1)
    tool_name: str
    input_summary: str
    output_summary: str
    status: StepStatus
    est_cost_usd: float | None = None
    duration_ms: float = Field(ge=0.0)


class AgentAskRequest(StrictContractModel):
    """Request payload for POST /agent/ask."""

    query: str = Field(min_length=1)
    max_steps: int | None = None
    budget_usd: float | None = None
    model_tier: Literal["fast", "balanced", "deep"] = "balanced"
    attachment_text: str | None = None



class AgentAskResponse(StrictContractModel):
    """Response payload for POST /agent/ask."""

    query: str
    answer: str
    steps: list[AgentStep]
    total_cost_usd: float | None = None
    cost: float | None = None
    duration_ms: float = Field(ge=0.0)
    model_tier: str = "balanced"
    is_placeholder: bool = False
    disclaimer: str = (
        "Educational and research review only. FinInsight does not provide "
        "investment recommendations or financial advice."
    )
