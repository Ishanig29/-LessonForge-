"""Typed application errors that map cleanly onto HTTP responses."""
from __future__ import annotations


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, details: dict | list | None = None, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.details = details
        if code:
            self.code = code

    def to_dict(self) -> dict:
        body = {"error": {"code": self.code, "message": self.message}}
        if self.details is not None:
            body["error"]["details"] = self.details
        return body


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_error"


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class MissingCredentials(AppError):
    """A required API key is not configured."""

    status_code = 503
    code = "missing_credentials"


class ExternalServiceError(AppError):
    """An upstream API (Gemini, Tavily, Books, YouTube) failed."""

    status_code = 502
    code = "external_service_error"


class RateLimited(ExternalServiceError):
    status_code = 429
    code = "rate_limited"


class AIOutputInvalid(AppError):
    """The model returned JSON that failed schema validation after retries."""

    status_code = 502
    code = "ai_output_invalid"


class TimingLimitExceeded(AppError):
    status_code = 422
    code = "timing_limit_exceeded"
