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

