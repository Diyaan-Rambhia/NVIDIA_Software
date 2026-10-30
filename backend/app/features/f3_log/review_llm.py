"""Feature 3 review text generation per PROJECT.md §5.11, §9, and PROGRESS.md X9.7."""

import logging
from typing import Any

from backend.app.contracts.portfolio import DecisionReview
from backend.app.llm.guard import assert_no_financial_advice

logger = logging.getLogger("backend.app.features.f3_log.review_llm")


def generate_decision_review_narrative(
    review: DecisionReview,
    provider: Any = None,
    settings: Any = None,
    user_id: Any = None,
) -> str:
    """Generate educational process-versus-outcome review narrative from computed metrics.

    Uses live LLM (Nemotron deep tier) when configured, falling back gracefully to deterministic synthesis.
    Strictly excludes buy/sell/hold advice.
    """
    pm = review.process_metrics
    disp = pm.disposition_effect or {}
    pgr = disp.get("pgr", 0.0)
    plr = disp.get("plr", 0.0)

    # 1. Try real LLM completion via Nebius client if configured and not placeholder provider
    if settings is not None and not provider:
        try:
            api_key = settings.get_var_value("NEBIUS_API_KEY")
            if api_key:
                from backend.app.llm.client import LLMClient
                from backend.app.llm.registry import ModelRegistry

                registry = ModelRegistry(settings=settings)
                registry.initialize()
                client = LLMClient(registry=registry, settings=settings)

                bm_summary = "N/A"
                if review.benchmark_replays:
                    bm = review.benchmark_replays[0]
                    bm_xirr_str = f"{bm.xirr * 100:.2f}%" if bm.xirr is not None else "no root"
                    bm_summary = f"{bm.benchmark_name} replay XIRR: {bm_xirr_str}"

                xirr_val = f"{review.portfolio_xirr * 100:.2f}%" if review.portfolio_xirr is not None else "N/A"
                prefix = f"{review.synthetic_label}. " if (review.is_synthetic_demo and review.synthetic_label) else ""

                sys_prompt = (
                    "You are FinInsight's Quantitative Behavioral Reviewer. "
                    "Analyze the computed trade execution metrics and provide an educational review narrative. "
                    "CRITICAL RULES:\n"
                    "1. Purely educational and analytical. Absolutely NO financial advice, NO buy, sell, or hold recommendations, NO price targets.\n"
                    "2. Cite only the computed metrics provided: portfolio XIRR, benchmark replay XIRR, turnover, concentration HHI, and disposition effect (PGR/PLR).\n"
                    "3. Plain prose only (3 to 5 sentences). Never emit markdown code blocks, JSON, or bullet points.\n"
                    "4. Conclude with: Educational and research review only. FinInsight does not provide investment recommendations or financial advice."
                )

                user_prompt = (
                    f"Computed Execution Metrics:\n"
                    f"- Portfolio Money-Weighted XIRR: {xirr_val}\n"
                    f"- Benchmark Replay: {bm_summary}\n"
                    f"- Portfolio Turnover: {pm.turnover:.2f}\n"
                    f"- Concentration HHI: {pm.concentration_hhi:.4f}\n"
                    f"- Disposition Effect: PGR={pgr:.2f}, PLR={plr:.2f}\n\n"
                    f"Provide the educational behavioral review narrative in plain prose."
                )

                resp = client.complete(
                    alias="deep",
                    messages=[
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    user_id=user_id,
                    route="/f3/review",
                    temperature=0.0,
                )

                choice = resp.get("choices", [{}])[0]
                content = choice.get("message", {}).get("content", "").strip()
                if content:
                    assert_no_financial_advice(content)
                    full_text = f"{prefix}{content}" if (prefix and prefix not in content) else content
                    return full_text
        except Exception as exc:
            logger.warning("Live LLM narrative generation fallback to deterministic: %s", exc)

    # 2. Deterministic narrative fallback
    lines: list[str] = []

    if getattr(provider, "is_placeholder", False):
        marker = getattr(provider, "placeholder_label", "PLACEHOLDER TEMPLATE, not Nemotron")
        lines.append(f"{marker}.")

    if review.is_synthetic_demo and review.synthetic_label:
        lines.append(f"{review.synthetic_label}.")

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
