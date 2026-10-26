"""Cost report aggregator per PROJECT.md §4.8 (FR-CAC-004), §7.1 and PROGRESS.md A3.3."""

from typing import Any

from backend.app.contracts.common import StrictContractModel
from backend.app.infra.budget_guard import calculate_call_cost


class UsageRecord(StrictContractModel):
    """Single LLM usage ledger row per PROJECT.md §7.1."""

    timestamp: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float | None = None
    cache_hit: bool = False
    user_id: str | None = None
    route: str | None = None


class ModelUsageSummary(StrictContractModel):
    """Aggregated usage and cost summary for a single model."""

    call_count: int
    input_tokens: int
    output_tokens: int
    cost_usd: float | None = None
    cost_status: str = "known"
    cache_hits: int


class DayUsageSummary(StrictContractModel):
    """Aggregated usage and cost summary for a single UTC calendar day."""

    call_count: int
    input_tokens: int
    output_tokens: int
    cost_usd: float | None = None
    cost_status: str = "known"
    cache_hits: int


class CostReportSummary(StrictContractModel):
    """Overall aggregated cost report."""

    total_spend_usd: float | None = None
    cost_status: str = "known"
    total_calls: int
    total_input_tokens: int
    total_output_tokens: int
    cache_hits: int
    cache_misses: int
    by_model: dict[str, ModelUsageSummary]
    by_day: dict[str, DayUsageSummary]


def _extract_day_key(timestamp_str: str) -> str:
    """Extract UTC calendar date YYYY-MM-DD from ISO timestamp string."""
    clean = timestamp_str.strip()
    return clean[:10]


def aggregate_cost_report(
    records: list[UsageRecord],
    pricing_table: dict[str, Any] | None = None,
) -> CostReportSummary:
    """Aggregate a list of LLM usage records into totals per model and per day.

    If pricing is unset or cost is unknown, cost is recorded as null and cost_status='unknown'.
    """
    total_spend = 0.0
    total_input = 0
    total_output = 0
    total_hits = 0
    total_misses = 0
    has_unknown_total = False

    by_model_acc: dict[str, dict[str, Any]] = {}
    by_day_acc: dict[str, dict[str, Any]] = {}

    for rec in records:
        cost: float | None = None
        if rec.cost_usd is not None:
            cost = rec.cost_usd
        elif pricing_table is not None and rec.model in pricing_table:
            cost = calculate_call_cost(
                model=rec.model,
                input_tokens=rec.input_tokens,
                output_tokens=rec.output_tokens,
                pricing_table=pricing_table,
            )
        else:
            cost = None
            has_unknown_total = True

        if cost is not None:
            total_spend += cost
        total_input += rec.input_tokens
        total_output += rec.output_tokens
        if rec.cache_hit:
            total_hits += 1
        else:
            total_misses += 1

        # Per model
        m_entry = by_model_acc.setdefault(
            rec.model,
            {
                "call_count": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
                "cache_hits": 0,
                "unknown_costs": False,
            },
        )
        m_entry["call_count"] += 1
        m_entry["input_tokens"] += rec.input_tokens
        m_entry["output_tokens"] += rec.output_tokens
        if cost is not None:
            m_entry["cost_usd"] += cost
        else:
            m_entry["unknown_costs"] = True
        if rec.cache_hit:
            m_entry["cache_hits"] += 1

        # Per day
        day_key = _extract_day_key(rec.timestamp)
        d_entry = by_day_acc.setdefault(
            day_key,
            {
                "call_count": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
                "cache_hits": 0,
                "unknown_costs": False,
            },
        )
        d_entry["call_count"] += 1
        d_entry["input_tokens"] += rec.input_tokens
        d_entry["output_tokens"] += rec.output_tokens
        if cost is not None:
            d_entry["cost_usd"] += cost
        else:
            d_entry["unknown_costs"] = True
        if rec.cache_hit:
            d_entry["cache_hits"] += 1

    by_model_result = {
        m: ModelUsageSummary(
            call_count=data["call_count"],
            input_tokens=data["input_tokens"],
            output_tokens=data["output_tokens"],
            cost_usd=round(data["cost_usd"], 6) if not data["unknown_costs"] else None,
            cost_status="unknown" if data["unknown_costs"] else "known",
            cache_hits=data["cache_hits"],
        )
        for m, data in sorted(by_model_acc.items())
    }

    by_day_result = {
        d: DayUsageSummary(
            call_count=data["call_count"],
            input_tokens=data["input_tokens"],
            output_tokens=data["output_tokens"],
            cost_usd=round(data["cost_usd"], 6) if not data["unknown_costs"] else None,
            cost_status="unknown" if data["unknown_costs"] else "known",
            cache_hits=data["cache_hits"],
        )
        for d, data in sorted(by_day_acc.items())
    }

    return CostReportSummary(
        total_spend_usd=round(total_spend, 6) if not has_unknown_total else None,
        cost_status="unknown" if has_unknown_total else "known",
        total_calls=len(records),
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        cache_hits=total_hits,
        cache_misses=total_misses,
        by_model=by_model_result,
        by_day=by_day_result,
    )
