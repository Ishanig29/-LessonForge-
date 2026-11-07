"""Small HTTP helper with timeouts, bounded retries and typed errors."""
from __future__ import annotations

import logging
import time

import requests

from .errors import ExternalServiceError, RateLimited

log = logging.getLogger("lessonforge.http")

RETRYABLE_STATUS = {500, 502, 503, 504}


def request_json(
    method: str,
    url: str,
    *,
    service: str,
    timeout: int = 25,
    max_retries: int = 2,
    backoff: float = 1.5,
    **kwargs,
) -> dict:
    """Perform a request and return JSON, retrying transient failures.

    ``service`` is a human label used in error messages ("Tavily", "YouTube").
    Query strings are not logged because some APIs take the key as a parameter.
    """
    delay = backoff
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = requests.request(method, url, timeout=timeout, **kwargs)
        except requests.Timeout as exc:
            last_exc = ExternalServiceError(f"{service} request timed out.", code="timeout")
            log.warning("http.timeout service=%s attempt=%s", service, attempt + 1)
        except requests.RequestException as exc:
            last_exc = ExternalServiceError(f"Could not reach {service}: network error.", code="network_error")
            log.warning("http.network service=%s attempt=%s err=%s", service, attempt + 1, type(exc).__name__)
        else:
            if resp.status_code == 429:
                last_exc = RateLimited(f"{service} rate limit reached. Please wait and retry.")
            elif resp.status_code in (401, 403):
                raise ExternalServiceError(
                    f"{service} rejected the credentials (HTTP {resp.status_code}). "
                    "Check that the API key is valid, enabled for this API and has quota.",
                    code="invalid_credentials",
                )
            elif resp.status_code in RETRYABLE_STATUS:
                last_exc = ExternalServiceError(f"{service} is temporarily unavailable (HTTP {resp.status_code}).")
            elif resp.status_code >= 400:
                raise ExternalServiceError(f"{service} request failed (HTTP {resp.status_code}).")
            else:
                try:
                    return resp.json()
                except ValueError as exc:
                    raise ExternalServiceError(f"{service} returned a non-JSON response.") from exc
        if attempt < max_retries:
            time.sleep(delay)
            delay *= 2
    assert last_exc is not None
    raise last_exc
