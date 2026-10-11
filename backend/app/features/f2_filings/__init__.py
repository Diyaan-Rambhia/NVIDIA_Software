"""Feature 2 Filing Consistency Checker package."""

from backend.app.features.f2_filings.derived_metrics import (
    dso,
    margin,
    ocf_conversion,
    q4_derivation,
    qoq_growth,
    yoy_growth,
)
from backend.app.features.f2_filings.quote_verifier import (
    verify_claim_quote,
    verify_quote,
)
from backend.app.features.f2_filings.rules import (
    RuleResult,
    RuleSeverity,
    RuleStatus,
    evaluate_all_rules,
    evaluate_r0_stated_number,
    evaluate_r1_direction,
    evaluate_r2_magnitude,
    evaluate_r3_trend,
    evaluate_r4_profitability,
    evaluate_r5_cash_quality,
    evaluate_r6_working_capital,
    evaluate_r7_understatement,
    validate_alignment,
)
from backend.app.features.f2_filings.text_chunker import (
    TextChunk,
    chunk_text,
)

__all__ = [
    "RuleResult",
    "RuleSeverity",
    "RuleStatus",
    "TextChunk",
    "chunk_text",
    "dso",
    "evaluate_all_rules",
    "evaluate_r0_stated_number",
    "evaluate_r1_direction",
    "evaluate_r2_magnitude",
    "evaluate_r3_trend",
    "evaluate_r4_profitability",
    "evaluate_r5_cash_quality",
    "evaluate_r6_working_capital",
    "evaluate_r7_understatement",
    "margin",
    "ocf_conversion",
    "q4_derivation",
    "qoq_growth",
    "validate_alignment",
    "verify_claim_quote",
    "verify_quote",
    "yoy_growth",
]
