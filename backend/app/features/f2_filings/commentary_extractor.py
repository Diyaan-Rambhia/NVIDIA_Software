"""Management Commentary and Earnings Call transcript extraction pipeline.

Per PROJECT.md §4.4, §5.10, and FR-F2-002..005.
Extracts structured guidance, revenue drivers, margin pressures, capex plans,
and forward risks with exact character offsets for quote verification.
"""

import re
from dataclasses import dataclass
from typing import Literal

from backend.app.contracts.filings import Claim, FilingMetric, Inconsistency
from backend.app.features.f2_filings.quote_verifier import verify_quote

CommentarySection = Literal[
    "guidance",
    "revenue_commentary",
    "margin_commentary",
    "capex_commentary",
    "risks_and_headwinds",
]

CommentaryTone = Literal["optimistic", "cautious", "neutral"]


@dataclass(frozen=True)
class CommentaryItem:
    """Extracted management commentary segment with exact offsets."""

    section: CommentarySection
    quote: str
    start: int
    end: int
    tone: CommentaryTone
    has_target: bool = False
    target_metric: str | None = None
    target_value: float | None = None


# Patterns for identifying management commentary sections and targets
SECTION_PATTERNS: list[tuple[CommentarySection, re.Pattern[str], str | None]] = [
    (
        "guidance",
        re.compile(
            r"((?:we\s+expect|guidance\s+for|projecting|outlook\s+for|revising\s+(?:our\s+)?(?:revenue|margin)|operating\s+margin\s+guidance|revenue\s+growth\s+guidance|targeted\s+growth|management\s+reported)(?:(?!\.\s|\.\n)[\s\S])*?(?:revenue|margin|ebitda|growth|constant\s+currency|[0-9]+%)(?:(?!\.\s|\.\n)[\s\S])*)(?=\.|\n\n|$)",
            re.IGNORECASE,
        ),
        None,
    ),
    (
        "margin_commentary",
        re.compile(
            r"((?:operating\s+(?:profit\s+)?margins?|ebitda\s+margins?|gross\s+margins?|margins?)(?:(?!\.\s|\.\n)[\s\S])*?(?:expanded|are\s+at|stood\s+at|contracted|compressed|under\s+pressure|impacted\s+by|were\s+up|has\s+come\s+down|came\s+down)(?:(?!\.\s|\.\n)[\s\S])*?(?:basis\s+points|bps|[0-9]+(?:\.[0-9]+)?%?)(?:(?!\.\s|\.\n)[\s\S])*)(?=\.|\n\n|$)",
            re.IGNORECASE,
        ),
        "operating margin",
    ),
    (
        "revenue_commentary",
        re.compile(
            r"((?:(?:our\s+)?(?:revenue|net\s+sales|total\s+sales|sales\s+volume)\s+(?:grew|was|stood|reached)|registered\s+(?:the\s+)?(?:highest\s+ever\s+)?(?:net\s+sales|revenue)|(?:revenue|sales|volume)\s+growth|sales\s+volume|topline\s+performance)(?:(?!\.\s|\.\n)[\s\S])*?(?:driven\s+by|led\s+by|supported\s+by|slowed\s+down|quarter-on-quarter|sequentially|year-on-year|yoy|against|constant\s+currency|growth\s+of|inr|[0-9]+(?:\.[0-9]+)?%)(?:(?!\.\s|\.\n)[\s\S])*)(?=\.|\n\n|$)",
            re.IGNORECASE,
        ),
        "revenue from operations",
    ),
    (
        "capex_commentary",
        re.compile(
            r"((?:free\s+cash\s+flow|cash\s+flow|large\s+deal\s+tcv|net\s+new\s+deal|deal\s+wins|capital\s+expenditure|capex|net\s+profit|profit\s+after\s+tax)(?:(?!\.\s|\.\n)[\s\S])*?(?:₹|rs\.?|inr|\$|[0-9]+(?:\.[0-9]+)?\s*(?:bn|billion|mn|million|cr|crore|crores|%))(?:(?!\.\s|\.\n)[\s\S])*)(?=\.|\n\n|$)",
            re.IGNORECASE,
        ),
        "capital expenditure",
    ),
    (
        "risks_and_headwinds",
        re.compile(
            r"((?:headwinds|macro\s+uncertainty|regulatory\s+scrutiny|supply\s+chain\s+disruptions|inflationary\s+pressures|furloughs)(?:(?!\.\s|\.\n)[\s\S])*?(?:spending|growth|compensation|furloughs|demand|disruptions)(?:(?!\.\s|\.\n)[\s\S])*)(?=\.|\n\n|$)",
            re.IGNORECASE,
        ),
        None,
    ),
]


def extract_commentary_items(source_text: str) -> list[CommentaryItem]:
    """Parse text into categorized commentary items with exact character offsets."""
    if not source_text or not source_text.strip():
        return []

    items: list[CommentaryItem] = []

    for section, pattern, default_metric in SECTION_PATTERNS:
        for match in pattern.finditer(source_text):
            quote = match.group(0).strip()
            start = match.start()
            end = match.start() + len(quote)

            # Strict verbatim check
            if source_text[start:end] != quote:
                continue

            q_lower = quote.lower()
            if any(w in q_lower for w in ["headwind", "pressure", "uncertainty", "contracted", "compressed", "slowed", "decline"]):
                tone: CommentaryTone = "cautious"
            elif any(w in q_lower for w in ["expanded", "expansion", "driven by", "led by", "strong", "accelerated", "exceeding", "grew", "growth", "increase", "higher", "improved", "record"]):
                tone = "optimistic"
            else:
                tone = "neutral"

            # Determine specific metric target
            target_metric = default_metric
            if section == "guidance":
                if "margin" in q_lower:
                    target_metric = "operating margin"
                elif "pat" in q_lower or "profit" in q_lower:
                    target_metric = "profit after tax"
                else:
                    target_metric = "revenue from operations"

            num_match = re.search(r"([0-9]+(?:\.[0-9]+)?)", quote)
            target_val = float(num_match.group(1)) if num_match else None

            items.append(
                CommentaryItem(
                    section=section,
                    quote=quote,
                    start=start,
                    end=end,
                    tone=tone,
                    has_target=target_val is not None,
                    target_metric=target_metric,
                    target_value=target_val,
                )
            )

    return items


def audit_guidance_against_metrics(
    commentary_items: list[CommentaryItem],
    filed_metrics: list[FilingMetric],
    source_text: str,
) -> list[Inconsistency]:
    """Adjudicate management guidance against realized XBRL filing figures."""
    inconsistencies: list[Inconsistency] = []
    metrics_by_name = {m.metric.lower(): m for m in filed_metrics}

    for item in commentary_items:
        if item.section == "guidance" and item.target_value is not None:
            # Check revenue or margin guidance discrepancy
            metric_target = item.target_metric or "revenue from operations"
            filed = metrics_by_name.get(metric_target.lower())
            if filed and filed.value is not None:
                diff = abs(item.target_value - filed.value)
                if diff > 2.0:  # Material divergence > 2 percentage points
                    inc = Inconsistency(
                        rule_id="R0_GUIDANCE_DIVERGENCE",
                        verdict="confirm",
                        severity="high" if diff > 5.0 else "medium",
                        metric=metric_target,
                        claim_quote=item.quote,
                        quote_start=item.start,
                        quote_end=item.end,
                        stated_value=item.target_value,
                        filed_value=filed.value,
                        difference_value=round(diff, 2),
                        explanation=(
                            f"Management stated target of {item.target_value}% in guidance, "
                            f"diverging from realized filing figure of {filed.value}% by {diff:.2f} percentage points."
                        ),
                    )
                    if verify_quote(source_text, inc.claim_quote, inc.quote_start, inc.quote_end):
                        inconsistencies.append(inc)

    return inconsistencies
