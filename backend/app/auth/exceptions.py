"""Authentication exceptions for FinInsight."""


class AuthError(Exception):
    """Base exception for authentication failures."""

    def __init__(self, message: str, code: str = "AUTH_ERROR", status_code: int = 401) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class MissingTokenError(AuthError):
    """Raised when the authorization header or token is missing."""

    def __init__(self, message: str = "Authorization token is missing") -> None:
        super().__init__(message=message, code="missing_token", status_code=401)


class InvalidTokenError(AuthError):
    """Raised when token signature or payload is invalid."""

    def __init__(self, message: str = "Invalid token") -> None:
        super().__init__(message=message, code="invalid_token", status_code=401)


class ExpiredTokenError(AuthError):
    """Raised when token is expired."""

    def __init__(self, message: str = "Token has expired") -> None:
        super().__init__(message=message, code="token_expired", status_code=401)


class EmailNotVerifiedError(AuthError):
    """Raised when token is valid but email has not been verified."""

    def __init__(self, message: str = "Email verification is required before access") -> None:
        super().__init__(message=message, code="email_not_verified", status_code=403)


class ForbiddenError(AuthError):
    """Raised when an authenticated user lacks required permissions."""

    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(message=message, code="forbidden", status_code=403)
