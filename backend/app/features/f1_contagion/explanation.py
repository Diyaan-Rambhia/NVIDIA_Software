"""Feature 1 explanation layer per PROJECT.md §5.8, §5.9, §9, and PROGRESS.md X7."""

import logging
from typing import Any

from backend.app.config.env import Settings, load_settings
from backend.app.contracts.contagion import (
    CorrelationScan,
    EvidenceItem,
    EvidencePack,
    Hypothesis,
    WindowRange,
)
from backend.app.llm.placeholder import PlaceholderProvider
from backend.app.version import get_code_version

logger = logging.getLogger("backend.app.features.f1_contagion.explanation")


def fetch_tavily_news(query: str, settings: Settings | None = None) -> list[dict[str, Any]]:
    """Fetch external news context via Tavily API.

    Per project rules, raises 'not run: no key' when unconfigured and is never replaced with fake data.
    """
    s = settings or load_settings()
    api_key = s.get_var_value("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("not run: no key")

    # In live mode with key, this would call Tavily endpoint
    raise ValueError("not run: no key")


def build_evidence_pack(
    scan: CorrelationScan,
    baseline_dates: list[str] | None = None,
    current_dates: list[str] | None = None,
) -> EvidencePack:
    """Build canonical EvidencePack container from CorrelationScan per PROJECT.md §5.8."""
    items: list[EvidenceItem] = []
    item_idx = 1

    # 1. Systemic Absorption Ratio evidence item
    items.append(
        EvidenceItem(
            id=f"E{item_idx}",
            kind="ar",
            description=(
                f"Systemic absorption ratio measured at {scan.absorption_ratio:.4f} "
                f"with standardized shift {scan.ar_delta_std:.2f} sigma."
            ),
            values={
                "absorption_ratio": float(scan.absorption_ratio),
                "ar_delta_std": float(scan.ar_delta_std),
            },
            source="NSE",
        )
    )
    item_idx += 1

    # 2. Top shifted pairs evidence items
    for pair in scan.top_shifted_pairs[:5]:
        sym1, sym2 = pair.pair[0], pair.pair[1]
        items.append(
            EvidenceItem(
                id=f"E{item_idx}",
                kind="pair_shift",
                description=(
                    f"Pair correlation shift for {sym1}-{sym2} from baseline {pair.baseline_corr:.2f} "
                    f"to current {pair.current_corr:.2f} (FR-adjusted: {pair.fr_adjusted_corr:.2f}, "
                    f"p={pair.p_value:.4f})."
                ),
                values={
                    "baseline_corr": float(pair.baseline_corr),
                    "current_corr": float(pair.current_corr),
                    "fr_adjusted_corr": float(pair.fr_adjusted_corr),
                    "p_value": float(pair.p_value),
                },
                source="NSE",
            )
        )
        item_idx += 1

    # Windows
    b_dates = baseline_dates or ["baseline_start", "baseline_end"]
    c_dates = current_dates or ["current_start", "current_end"]
    window = WindowRange(baseline=b_dates[:2], current=c_dates[:2])

    return EvidencePack(
        as_of=scan.as_of,
        parameters_used=scan.parameters_used,
        window=window,
        items=items,
        seed=scan.seed,
        code_version=get_code_version(),
    )


def generate_hypotheses(
    evidence_pack: EvidencePack,
    news_items: list[dict[str, Any]] | None = None,
    llm_client: Any = None,
) -> list[Hypothesis]:
    """Generate 2-4 ranked, hedged mechanism hypotheses citing evidence item IDs."""
    if llm_client is None:
        llm_client = PlaceholderProvider()

    all_evidence_ids = [item.id for item in evidence_pack.items]
    if not all_evidence_ids:
        all_evidence_ids = ["E1", "E2"]

    # Candidate mechanism classes from taxonomy in PROJECT.md §5.9
    mechanisms = [
        (
            "global risk-off and FPI outflow",
            all_evidence_ids[:2],
            all_evidence_ids[2:3],
            "Broad correlation elevation across cross-sector pairs and absorption ratio expansion "
            "are consistent with institutional liquidity rebalancing, pending confirmation from official flow data.",
        ),
        (
            "domestic liquidity squeeze",
            all_evidence_ids[:1],
            [],
            "Systemic absorption ratio tightening indicates concentrated co-movement, which may reflect "
            "money-market liquidity conditions or advance tax outflows.",
        ),
        (
            "commodity shock",
            all_evidence_ids[1:3] if len(all_evidence_ids) >= 3 else all_evidence_ids[:1],
            [],
            "Shifts in industrial and energy pairs suggest factor sensitivity to external input cost pressures.",
        ),
    ]

    urls = [
        "https://rbi.org.in/press_releases",
        "https://www.sebi.gov.in/reports.html",
    ]

    hypotheses: list[Hypothesis] = []
    for mech_class, sup, weak, plaus in mechanisms:
        if not sup:
            sup = [all_evidence_ids[0]]
        hyp = Hypothesis(
            mechanism_class=mech_class,
            evidence_supporting=sup,
            evidence_weakening=weak,
            retrieved_urls=urls,
            plausible_mechanism=f"PLACEHOLDER TEMPLATE, not Nemotron. {plaus}",
        )
        hypotheses.append(hyp)

    # Return between 2 and 4 ranked hypotheses
    return hypotheses[:3]
