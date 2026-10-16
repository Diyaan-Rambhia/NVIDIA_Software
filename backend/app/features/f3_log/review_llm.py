"""Feature 3 review text generation per PROJECT.md §5.11, §9, and PROGRESS.md X9.7."""

import logging
from typing import Any

from backend.app.contracts.portfolio import DecisionReview
from backend.app.llm.guard import assert_no_financial_advice
from backend.app.llm.placeholder import PlaceholderProvider

logger = logging.getLogger("backend.app.features.f3_log.review_llm")

PLACEHOLDER_MARKER = "PLACEHOLDER TEMPLATE, not Nemotron"


def generate_decision_review_narrative(
    review: DecisionReview,
    llm_client: Any = None,
) -> str:
    """Generate educational process-versus-outcome review narrative from computed metrics.

    Preserves synthetic demo log label if present and strictly excludes buy/sell/hold advice.
    """
    if llm_client is None:
        llm_client = PlaceholderProvider()

    pm = review.process_metrics
    port = review.portfolio
    disp = pm.disposition_effect
    pgr = disp.get("pgr", 0.0)
    plr = disp.get("plr", 0.0)

    # Narrative framing process versus outcome
    lines: list[str] = []

    if review.is_synthetic_demo or review.synthetic_label:
        lines.append(f"{review.synthetic_label or 'SYNTHETIC DEMO LOG, not a real investor'}.")

    lines.append(f"{PLACEHOLDER_MARKER}.")
    lines.append(
        "Process-versus-outcome evaluation: Portfolio turnover was recorded at "
        f"{pm.turnover:.2f} with concentration HHI of {pm.concentration_hhi:.4f}."
    )

    if pgr > 0 or plr > 0:
        lines.append(
            f"Disposition analysis shows Proportion of Gains Realized (PGR) at {pgr:.2f} "
            f"and Proportion of Losses Realized (PLR) at {plr:.2f}."
        )

    if review.portfolio_xirr is not None and review.benchmark_replays:
        bm = review.benchmark_replays[0]
        bm_xirr_str = f"{bm.xirr * 100:.2f}%" if bm.xirr is not None else "no root"
        lines.append(
            f"Observed portfolio XIRR of {review.portfolio_xirr * 100:.2f}% compared against "
            f"{bm.benchmark_name} replay XIRR of {bm_xirr_str}."
        )

    lines.append(
        "Educational and research review only. Past execution patterns do not indicate "
        "future returns. This analysis does not provide investment recommendations."
    )

    review_text = " ".join(lines)

    # Output guard validation
    assert_no_financial_advice(review_text)

    return review_text
