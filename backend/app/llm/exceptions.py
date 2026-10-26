"""Exceptions for the LLM gateway and guardrails."""


class LLMError(Exception):
    """Base exception for LLM gateway operations."""

    def __init__(self, message: str, code: str = "LLM_ERROR", status_code: int = 500) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class ModelResolutionError(LLMError):
    """Raised when a model alias cannot be resolved from the live catalog."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="MODEL_RESOLUTION_ERROR", status_code=502)


class BudgetExceededError(LLMError):
    """Raised when an LLM call would exceed the daily spend budget."""

    def __init__(self, message: str = "Daily LLM budget exceeded") -> None:
        super().__init__(message=message, code="BUDGET_EXCEEDED", status_code=429)


class FinancialAdviceError(LLMError):
    """Raised when LLM output contains prohibited buy, sell, or hold advice."""

    def __init__(self, message: str = "Output contains prohibited financial advice") -> None:
        super().__init__(message=message, code="FINANCIAL_ADVICE_PROHIBITED", status_code=422)


class LLMTimeoutError(LLMError):
    """Raised when an LLM call times out."""

    def __init__(self, message: str = "LLM upstream request timed out") -> None:
        super().__init__(message=message, code="LLM_TIMEOUT", status_code=504)


class LLMUpstreamError(LLMError):
    """Raised when the upstream LLM provider returns an HTTP error."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(
            message=f"Upstream provider error ({status_code}): {message}",
            code=f"UPSTREAM_HTTP_{status_code}",
            status_code=status_code if status_code in (401, 403, 429) else 502,
        )


class ProviderNotConfiguredError(RuntimeError, LLMError):
    """Raised when no real LLM provider is configured in production."""

    def __init__(
        self,
        message: str = (
            "No real LLM provider is configured in production. "
            "Placeholder provider is strictly forbidden in production."
        ),
    ) -> None:
        RuntimeError.__init__(self, message)
        self.message = message
        self.code = "provider_not_configured"
        self.status_code = 503


class TierUnavailableError(LLMError):
    """Raised when a requested model tier is unavailable."""

    def __init__(self, tier: str, reason: str) -> None:
        message = f"Model tier '{tier}' is unavailable: {reason}"
        super().__init__(message=message, code="TIER_UNAVAILABLE", status_code=503)
        self.tier = tier
        self.reason = reason


class NonProseAnswerError(LLMError):
    """Raised when model returns code, JSON, or non-prose output."""

    def __init__(self, message: str = "model returned a non-prose answer") -> None:
        super().__init__(message=message, code="NON_PROSE_ANSWER", status_code=422)


class PriceNotSetError(LLMError):
    """Raised when a model tier's pricing is not configured in config/models.yaml (legacy)."""

    def __init__(self, tier: str) -> None:
        message = f"Pricing for model tier '{tier}' is not set. Calls to this model are refused."
        super().__init__(message=message, code="price_not_set", status_code=503)
        self.tier = tier


class TokenLimitExceededError(LLMError):
    """Raised when per-call or daily token limit is exceeded when price is unset."""

    def __init__(self, message: str, reset_time: str | None = None) -> None:
        super().__init__(message=message, code="quota_exceeded", status_code=429)
        self.reset_time = reset_time


class LedgerError(LLMError):
    """Raised when an operation on the LLM ledger fails."""

    def __init__(self, message: str = "LLM ledger operation failed") -> None:
        super().__init__(message=message, code="LEDGER_ERROR", status_code=500)


class ModelOutputInvalidError(LLMError):
    """Raised when model output fails JSON parsing or validation."""

    def __init__(self, message: str = "Model output is invalid or unparseable") -> None:
        super().__init__(message=message, code="MODEL_OUTPUT_INVALID", status_code=502)


class ModelToolCallFailedError(LLMError):
    """Raised when model returns no valid tool call after retry limit."""

    def __init__(self, tier: str, message: str | None = None) -> None:
        msg = message or f"502 MODEL_TOOL_CALL_FAILED: Tier '{tier}' returned no valid tool call after retry limit"
        super().__init__(message=msg, code="MODEL_TOOL_CALL_FAILED", status_code=502)
        self.tier = tier


