"""Filings feature contracts per PROJECT.md §4.4, §7.2, §7.3."""

from typing import Literal

from pydantic import model_validator

from backend.app.contracts.common import StrictContractModel

ClaimBasis = Literal["reported", "adjusted", "constant-currency", "unspecified"]
MetricBasis = Literal["standalone", "consolidated"]


class Claim(StrictContractModel):
    """Claim extracted from filing text per PROJECT.md §4.4, §7.3, and FR-F2-002."""

    metric: str
    descriptor: str
    direction: str
    quote: str
    start: int
    end: int
    period: str
    basis: ClaimBasis

    @model_validator(mode="after")
    def validate_offsets(self) -> "Claim":
        if self.end <= self.start:
            raise ValueError(
                f"Claim end offset ({self.end}) must be greater than start offset ({self.start})"
            )
        return self


class FilingMetric(StrictContractModel):
    """Normalized filing metric per PROJECT.md §7.2 and §7.3."""

    company: str
    symbol: str
    isin: str | None = None
    fiscal_period: str
    period_end_date: str
    basis: MetricBasis
    metric: str
    value: float
    unit: str
    source_filing_reference: str
    derived: bool
    retrieval_time: str


InconsistencyVerdict = Literal["confirm", "downgrade", "reject"]
InconsistencySeverity = Literal["high", "medium", "low"]


class Inconsistency(StrictContractModel):
    """Adjudicated filing inconsistency finding per PROJECT.md §5.10, §7.3, §9."""

    rule_id: str
    verdict: InconsistencyVerdict
    severity: InconsistencySeverity
    metric: str
    claim_quote: str
    quote_start: int
    quote_end: int
    stated_value: float | None = None
    filed_value: float | None = None
    difference_value: float | None = None
    explanation: str
    is_placeholder: bool = False
    placeholder_label: str | None = None

    @model_validator(mode="after")
    def validate_offsets(self) -> "Inconsistency":
        if self.quote_end <= self.quote_start:
            raise ValueError(
                f"Quote end offset ({self.quote_end}) must be greater than start offset ({self.quote_start})"
            )
        return self
