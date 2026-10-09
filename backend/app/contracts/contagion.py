"""Contagion feature contracts per PROJECT.md §5.8 and §5.9."""

import re
from typing import Literal

from pydantic import Field, field_validator, model_validator

from backend.app.contracts.common import StrictContractModel

EvidenceKind = Literal["pair_shift", "ar", "pc1_loading", "macro_assoc"]


class WindowRange(StrictContractModel):
    """Baseline and current date windows per PROJECT.md §5.8."""

    baseline: list[str] = Field(min_length=2, max_length=2)
    current: list[str] = Field(min_length=2, max_length=2)


class EvidenceItem(StrictContractModel):
    """Single item in EvidencePack per PROJECT.md §5.8."""

    id: str
    kind: EvidenceKind
    description: str
    values: dict[str, float]
    source: str

    @field_validator("id")
    @classmethod
    def validate_id_pattern(cls, v: str) -> str:
        if not re.match(r"^E\d+$", v):
            raise ValueError(f"EvidenceItem id must match pattern 'E<digits>', got {v!r}")
        return v


class EvidencePack(StrictContractModel):
    """Evidence pack container per PROJECT.md §5.8."""

    as_of: str
    parameters_used: dict[str, float | int | bool | str]
    window: WindowRange
    items: list[EvidenceItem]
    seed: int
    code_version: str

    @model_validator(mode="after")
    def validate_unique_item_ids(self) -> "EvidencePack":
        ids = [item.id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("EvidenceItem IDs within EvidencePack must be unique")
        return self


class Hypothesis(StrictContractModel):
    """Hypothesis structure per PROJECT.md §5.9, §7.3, §9, and FR-F1-011."""

    mechanism_class: str
    evidence_supporting: list[str] = Field(min_length=1)
    evidence_weakening: list[str]
    retrieved_urls: list[str] = Field(min_length=1)
    plausible_mechanism: str
