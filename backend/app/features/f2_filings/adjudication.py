"""Feature 2 claim extraction, deterministic matching, adjudication, and verifier.

Per PROJECT.md §5.10, §7.3, §9, and PROGRESS.md X8.
"""

import logging
import re
from typing import Any

from backend.app.contracts.filings import Claim, FilingMetric, Inconsistency
from backend.app.features.f2_filings.quote_verifier import verify_quote
from backend.app.features.f2_filings.rules import evaluate_r0_stated_number, evaluate_r1_direction
from backend.app.llm.exceptions import FinancialAdviceError
from backend.app.llm.guard import assert_no_financial_advice

logger = logging.getLogger("backend.app.features.f2_filings.adjudication")


def extract_claims_from_text(source_text: str, fiscal_period: str) -> list[Claim]:
    """Deterministically extract management claims with exact character offsets from announcement text."""
    claims: list[Claim] = []

    # Patterns matching metric statements with numbers or direction descriptors
    patterns = [
        (
            re.compile(
                r"(\brevenue\b[^\.\n]*?(?:grew|increased|rose|declined|fell)\s+by\s+([0-9]+(?:\.[0-9]+)?%?))",
                re.IGNORECASE,
            ),
            "revenue from operations",
        ),
        (
            re.compile(
                r"(\b(?:PAT|net profit|profit after tax)\b[^\.\n]*?(?:grew|increased|rose|declined|fell)\s+by\s+([0-9]+(?:\.[0-9]+)?%?))",
                re.IGNORECASE,
            ),
            "profit after tax",
        ),
        (
            re.compile(
                r"(\b(?:EBITDA|operating profit)\b[^\.\n]*?(?:grew|increased|expanded|declined)\s+by\s+([0-9]+(?:\.[0-9]+)?%?))",
                re.IGNORECASE,
            ),
            "operating profit",
        ),
    ]

    for regex, metric_name in patterns:
        for match in regex.finditer(source_text):
            quote = match.group(0)
            start = match.start()
            end = match.end()

            # Verify exact verbatim slice
            if source_text[start:end] != quote:
                continue

            direction = "increase" if any(w in quote.lower() for w in ["grew", "increased", "rose", "expanded"]) else "decline"
            descriptor = "stated number"

            claim = Claim(
                metric=metric_name,
                descriptor=descriptor,
                direction=direction,
                quote=quote,
                start=start,
                end=end,
                period=fiscal_period,
                basis="reported",
            )
            claims.append(claim)

    return claims


def verify_inconsistency_flag(inc: Inconsistency, source_text: str) -> bool:
    """Deterministic verifier blocking flags whose quote or number is not in source, or contains advice.

    Raises ValueError or FinancialAdviceError if verification fails.
    """
    # 1. Quote must exist verbatim at specified character offsets
    if not verify_quote(source_text, inc.claim_quote, inc.quote_start, inc.quote_end):
        raise ValueError(
            f"Blocked: quote '{inc.claim_quote}' does not match source text at [{inc.quote_start}:{inc.quote_end}]"
        )

    # 2. If a stated number is claimed, it must be literally present in source quote
    if inc.stated_value is not None:
        quote_slice = source_text[inc.quote_start:inc.quote_end]
        val_str = f"{inc.stated_value:g}"
        val_str_alt1 = f"{inc.stated_value:.1f}"
        val_str_alt2 = f"{inc.stated_value:.2f}"

        number_present = (
            val_str in quote_slice
            or val_str_alt1 in quote_slice
            or val_str_alt2 in quote_slice
        )
        if not number_present:
            raise ValueError(
                f"Blocked: stated number {inc.stated_value} is not literally present in source quote '{inc.claim_quote}'"
            )

    # 3. Output guard against financial advice
    assert_no_financial_advice(inc.explanation)
    assert_no_financial_advice(inc.claim_quote)

    return True


def match_and_adjudicate(
    claims: list[Claim],
    metrics: list[FilingMetric],
    source_text: str,
    provider: Any = None,
) -> list[Inconsistency]:
    """Match claims against normalized XBRL filing metrics, adjudicate, and verify."""
    inconsistencies: list[Inconsistency] = []
    metrics_by_name = {m.metric.lower(): m for m in metrics}

    for claim in claims:
        # Match metric
        matched_metric = metrics_by_name.get(claim.metric.lower())
        if not matched_metric:
            continue

        # Extract number if present in quote
        num_match = re.search(r"([0-9]+(?:\.[0-9]+)?)", claim.quote)
        stated_num = float(num_match.group(1)) if num_match else None

        # Check R0 Stated Number
        if stated_num is not None:
            r0_res = evaluate_r0_stated_number(
                claim=claim,
                metric=matched_metric,
                stated_value=stated_num,
                tolerance_pp=0.5,
            )
            if r0_res.status == "flag":
                diff = abs(stated_num - matched_metric.value)
                inc = Inconsistency(
                    rule_id="R0",
                    verdict="confirm",
                    severity="high",
                    metric=claim.metric,
                    claim_quote=claim.quote,
                    quote_start=claim.start,
                    quote_end=claim.end,
                    stated_value=stated_num,
                    filed_value=matched_metric.value,
                    difference_value=round(diff, 2),
                    explanation=(
                        f"Stated figure {stated_num} in announcement "
                        f"differs from filed XBRL value {matched_metric.value} by {diff:.2f} percentage points."
                    ),
                    is_placeholder=bool(getattr(provider, "is_placeholder", False)),
                    placeholder_label=getattr(provider, "placeholder_label", "PLACEHOLDER TEMPLATE, not Nemotron")
                    if getattr(provider, "is_placeholder", False)
                    else None,
                )
                # Verify deterministically before adding
                verify_inconsistency_flag(inc, source_text)
                inconsistencies.append(inc)

    return inconsistencies
