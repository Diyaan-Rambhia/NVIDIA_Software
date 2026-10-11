"""Budget guard logic per PROJECT.md §4.5 (FR-LLM-009) and PROGRESS.md A3.2."""

from datetime import datetime, timezone
from typing import Any

from backend.app.config.loader import ParameterError
from backend.app.contracts.common import StrictContractModel


class BudgetExceededError(ParameterError):
    """Raised when an uncached LLM call would reach or exceed the daily budget limit."""

    def __init__(self, spend_so_far: float, estimated_cost: float, limit: float) -> None:
        projected = spend_so_far + estimated_cost
        super().__init__(
            field="daily_budget",
            value=round(projected, 6),
            allowed_range=(0.0, limit),
            reason=(
                f"Projected spend ${projected:.6f} "
                f"(spend_so_far=${spend_so_far:.6f} + estimated_cost=${estimated_cost:.6f}) "
                f"reaches or exceeds daily limit ${limit:.6f}"
            ),
        )
        self.spend_so_far = spend_so_far
        self.estimated_cost = estimated_cost
        self.limit = limit


class UnknownModelPriceError(ParameterError):
    """Raised when a model cannot be priced because pricing is missing or marked pending."""

    def __init__(self, model: str) -> None:
        super().__init__(
            field="model_price",
            value=model,
            allowed_range="registered model pricing",
            reason=f"Model price for '{model}' is unknown or marked pending",
        )
        self.model = model


class ModelPrice(StrictContractModel):
    """Per-million token pricing for an LLM model."""

    input_price_per_million: float
    output_price_per_million: float


def calculate_call_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    pricing_table: dict[str, Any],
) -> float:
    """Calculate call cost in USD. Raises UnknownModelPriceError if unpriced or pending."""
    if input_tokens < 0:
        raise ParameterError(
            field="input_tokens",
            value=input_tokens,
            allowed_range=(0, None),
            reason="input_tokens cannot be negative",
        )
    if output_tokens < 0:
        raise ParameterError(
            field="output_tokens",
            value=output_tokens,
            allowed_range=(0, None),
            reason="output_tokens cannot be negative",
        )

    if model not in pricing_table:
        raise UnknownModelPriceError(model)

    price_entry = pricing_table[model]
    if price_entry is None or price_entry == "pending":
        raise UnknownModelPriceError(model)

    if isinstance(price_entry, ModelPrice):
        in_rate = price_entry.input_price_per_million
        out_rate = price_entry.output_price_per_million
    elif isinstance(price_entry, dict):
        has_in = "input_price_per_million" in price_entry
        has_out = "output_price_per_million" in price_entry
        if not (has_in and has_out):
            raise UnknownModelPriceError(model)
        in_val = price_entry["input_price_per_million"]
        out_val = price_entry["output_price_per_million"]
        if in_val is None or in_val == "pending" or out_val is None or out_val == "pending":
            raise UnknownModelPriceError(model)
        try:
            in_rate = float(in_val)
            out_rate = float(out_val)
        except (ValueError, TypeError) as exc:
            raise UnknownModelPriceError(model) from exc
    else:
        raise UnknownModelPriceError(model)

    return (input_tokens * in_rate / 1_000_000.0) + (output_tokens * out_rate / 1_000_000.0)


def check_budget_guard(
    spend_so_far: float,
    estimated_cost: float,
    daily_limit: float,
    now: datetime | None = None,
    reset_rule: str = "utc_midnight",
) -> bool:
    """Evaluate whether an LLM call is allowed under daily spend cap.

    Parameters
    ----------
    spend_so_far : float
        Current spend recorded today in USD.
    estimated_cost : float
        Estimated cost of the upcoming LLM call in USD.
    daily_limit : float
        Daily budget limit in USD (passed by caller: production vs test).
    now : datetime, optional
        Current timestamp for evaluating reset rule. If None, defaults to current UTC time.
    reset_rule : str, default 'utc_midnight'
        Calendar reset convention. Sourced from config, defaults to 'utc_midnight'.

    Returns
    -------
    bool
        True if the call is strictly permitted.

    Raises
    ------
    BudgetExceededError
        If projected spend (spend_so_far + estimated_cost) >= daily_limit.
    ParameterError
        If spend_so_far, estimated_cost, or daily_limit is negative.
    """
    if spend_so_far < 0.0:
        raise ParameterError(
            field="spend_so_far",
            value=spend_so_far,
            allowed_range=(0.0, None),
            reason="spend_so_far cannot be negative",
        )
    if estimated_cost < 0.0:
        raise ParameterError(
            field="estimated_cost",
            value=estimated_cost,
            allowed_range=(0.0, None),
            reason="estimated_cost cannot be negative",
        )
    if daily_limit <= 0.0:
        raise ParameterError(
            field="daily_limit",
            value=daily_limit,
            allowed_range=(0.0, None),
            reason="daily_limit must be strictly positive",
        )

    # Use now in UTC
    effective_now = now if now is not None else datetime.now(timezone.utc)
    if effective_now.tzinfo is None:
        effective_now = effective_now.replace(tzinfo=timezone.utc)

    # At or over the limit refuses
    projected = spend_so_far + estimated_cost
    if projected >= daily_limit:
        raise BudgetExceededError(spend_so_far, estimated_cost, daily_limit)

    return True
