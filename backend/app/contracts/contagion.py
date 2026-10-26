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


class ShiftedPair(StrictContractModel):
    """Pair correlation shift detail."""

    pair: list[str] = Field(min_length=2, max_length=2)
    baseline_corr: float
    current_corr: float
    fr_adjusted_corr: float
    p_value: float
    q_value: float


class NewsArticle(StrictContractModel):
    """External news article carrying evidence identifier."""

    title: str
    url: str
    content: str
    source: str | None = None
    evidence_id: str | None = None


class ContagionNews(StrictContractModel):
    """External macro news container with real execution state."""

    state: str = "not_run"  # "ready" | "results" | "empty" | "not_run" | "error"
    query: str | None = None
    results: list[NewsArticle] | None = None
    not_run_reason: str | None = None
    error_status: int | None = None
    error_message: str | None = None


class ContagionHypothesis(StrictContractModel):
    """Qualitative contagion hypothesis item."""

    id: str
    text: str
    evidence_ids: list[str] | None = None


class CorrelationScan(StrictContractModel):
    """Output contract for Feature 1 correlation scan per PROJECT.md §5.7 and §5.8."""

    as_of: str
    source_label: str = "market data, third-party, delayed"
    parameters_used: dict[str, float | int | bool | str]
    regime_flag: str
    absorption_ratio: float
    ar_delta_std: float
    significant_pairs_count: int
    mean_correlation: float
    top_shifted_pairs: list[ShiftedPair] = Field(default_factory=list)
    matrix_summary: dict[str, float | int] = Field(default_factory=dict)
    episodes_status: str = "pending_scan_full_history"
    seed: int
    code_version: str
    scan_duration_seconds: float = 0.0
    news: ContagionNews | None = None
    hypotheses: list[ContagionHypothesis] | None = None


