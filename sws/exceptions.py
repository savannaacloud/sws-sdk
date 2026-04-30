"""Exception hierarchy for the SWS SDK.

All errors derive from SWSError so callers can catch broadly with
`except SWSError:` or precisely with the subclasses below.
"""

from __future__ import annotations

from typing import Any


class SWSError(Exception):
    """Base class for all SDK errors."""


class APIError(SWSError):
    """Raised when the API returns a non-2xx response that is not a
    more specific error class below."""

    def __init__(self, status_code: int, message: str, body: Any = None) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"HTTP {status_code}: {message}")


class AuthenticationError(APIError):
    """API key is missing, invalid, or expired (401/403)."""


class NotFoundError(APIError):
    """Resource does not exist (404)."""


class ValidationError(APIError):
    """Request payload was rejected by the server (400/422)."""


class QuotaExceededError(APIError):
    """The tenant has hit a per-resource quota (403 with quota detail)."""
