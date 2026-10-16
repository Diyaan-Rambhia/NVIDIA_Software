"""Common contracts including the standard error envelope."""

from typing import Any

from pydantic import BaseModel, ConfigDict


class StrictContractModel(BaseModel):
    """Base model for all contracts forbidding extra fields."""

    model_config = ConfigDict(extra="forbid")


class ErrorDetail(StrictContractModel):
    """Inner error payload per FR-OBS-003 and §4.10."""

    code: str
    message: str
    request_id: str
    upstream: Any = None
    upgrade_targets: list[str] | None = None
    reset_time: str | None = None


class ErrorEnvelope(StrictContractModel):
    """Top-level error envelope per FR-OBS-003 and §4.10."""

    error: ErrorDetail
