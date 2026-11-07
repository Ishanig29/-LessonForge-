"""Provider-agnostic structured-output LLM client.

Every AI call in LessonForge goes through ``LLMClient.generate_json``:

1. The prompt is sent with JSON response mode enabled.
2. The text is parsed as JSON (tolerating code fences).
3. The object is validated against a Pydantic schema.
4. If parsing/validation fails, the model is re-asked once per retry with the
   validation error attached ("repair" turn).
5. Transient upstream errors (timeouts, 5xx, 429) are retried with
   exponential backoff. Auth/quota errors surface as typed AppErrors.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from ...utils.errors import (
    AIOutputInvalid,
    ExternalServiceError,
    MissingCredentials,
    RateLimited,
)

log = logging.getLogger("lessonforge.ai")
T = TypeVar("T", bound=BaseModel)


class LLMClient(Protocol):
    model_name: str
    is_demo: bool

    def generate_json(
        self, *, task: str, system: str, prompt: str, schema: type[T], temperature: float = 0.3
    ) -> T: ...


def extract_json(text: str) -> object:
    """Parse JSON from model text, tolerating ```json fences and leading prose."""
    if text is None:
        raise ValueError("Empty model response")
    cleaned = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.S)
    if fence:
        cleaned = fence.group(1)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(cleaned[start : end + 1])


def schema_hint(schema: type[BaseModel]) -> str:
    return json.dumps(schema.model_json_schema(), indent=None)[:12000]


class BaseJSONClient:
    """Shared parse/validate/repair loop. Subclasses implement ``_call``."""

    model_name = "unknown"
    is_demo = False

    def __init__(self, max_retries: int = 2, backoff_seconds: float = 2.0):
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds

    def _call(self, *, system: str, prompt: str, temperature: float) -> str:  # pragma: no cover
        raise NotImplementedError

    def generate_json(self, *, task, system, prompt, schema, temperature=0.3):
        full_prompt = (
            f"{prompt}\n\nReturn ONLY a JSON object that validates against this JSON Schema:\n"
            f"{schema_hint(schema)}"
        )
        last_error: str | None = None
        for attempt in range(self.max_retries + 1):
            turn = full_prompt
            if last_error:
                turn += (
                    "\n\nYour previous answer was rejected by the validator with this error:\n"
                    f"{last_error[:2000]}\nReturn a corrected, complete JSON object."
                )
            text = self._call_with_backoff(system=system, prompt=turn, temperature=temperature, task=task)
            try:
                data = extract_json(text)
                return schema.model_validate(data)
            except (ValueError, ValidationError) as exc:
                last_error = str(exc)
                log.warning("ai.invalid_output task=%s attempt=%s error=%s", task, attempt + 1, last_error[:300])
        raise AIOutputInvalid(
            f"The AI returned output that did not match the expected structure for '{task}' "
            f"after {self.max_retries + 1} attempts.",
            details={"last_error": (last_error or "")[:500]},
        )

    def _call_with_backoff(self, *, system, prompt, temperature, task) -> str:
        delay = self.backoff_seconds
        for attempt in range(self.max_retries + 1):
            try:
                started = time.monotonic()
                text = self._call(system=system, prompt=prompt, temperature=temperature)
                log.info("ai.call task=%s model=%s seconds=%.1f", task, self.model_name, time.monotonic() - started)
                return text
            except (RateLimited, ExternalServiceError) as exc:
                retryable = isinstance(exc, RateLimited) or exc.details == {"retryable": True}
                if not retryable or attempt == self.max_retries:
                    raise
                log.warning("ai.retry task=%s attempt=%s reason=%s", task, attempt + 1, exc.message)
                time.sleep(delay)
                delay *= 2
        raise ExternalServiceError("AI call failed")  # pragma: no cover


class GeminiClient(BaseJSONClient):
    """Google Gemini via the official ``google-genai`` SDK."""

    def __init__(self, api_key: str | None, model: str, timeout_seconds: int = 180, max_retries: int = 2):
        super().__init__(max_retries=max_retries)
        if not api_key:
            raise MissingCredentials(
                "Gemini API key is not configured. Set GEMINI_API_KEY in backend/.env to enable AI features.",
                details={"env_var": "GEMINI_API_KEY"},
            )
        from google import genai
        from google.genai import types

        self._types = types
        self.model_name = model
        self._client = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(timeout=timeout_seconds * 1000)
        )

    def _call(self, *, system: str, prompt: str, temperature: float) -> str:
        from google.genai import errors as genai_errors

        try:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=self._types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=temperature,
                    response_mime_type="application/json",
                ),
            )
        except genai_errors.APIError as exc:
            code = getattr(exc, "code", None)
            if code == 429:
                raise RateLimited("Gemini rate limit or quota exceeded. Wait and retry.") from exc
            if code in (401, 403):
                raise ExternalServiceError(
                    "Gemini rejected the API key (invalid, expired or lacking permission).",
                    code="invalid_credentials",
                ) from exc
            if code == 404:
                raise ExternalServiceError(
                    f"Gemini model '{self.model_name}' was not found. Check GEMINI_MODEL.",
                ) from exc
            retryable = code is None or code >= 500
            raise ExternalServiceError(
                f"Gemini request failed ({code}).", details={"retryable": True} if retryable else None
            ) from exc
        except Exception as exc:  # network errors / timeouts from the HTTP layer
            name = type(exc).__name__
            if "Timeout" in name or "timeout" in str(exc).lower():
                raise ExternalServiceError(
                    "Gemini request timed out.", details={"retryable": True}, code="ai_timeout"
                ) from exc
            raise ExternalServiceError(
                f"Could not reach Gemini ({name}).", details={"retryable": True}
            ) from exc
        text = getattr(response, "text", None)
        if not text:
            raise ExternalServiceError("Gemini returned an empty response (possibly blocked by safety filters).")
        return text
