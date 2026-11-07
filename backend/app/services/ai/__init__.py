"""AI provider factory. Routes and services obtain the client through
``get_llm()`` so tests can inject a fake via ``set_llm_override``."""
from __future__ import annotations

from flask import current_app

from ...utils.errors import MissingCredentials
from .client import BaseJSONClient, GeminiClient, LLMClient, extract_json  # noqa: F401

_override: LLMClient | None = None


def set_llm_override(client: LLMClient | None) -> None:
    global _override
    _override = client


def get_llm() -> LLMClient:
    if _override is not None:
        return _override
    settings = current_app.config["SETTINGS"]
    if settings.demo_mode:
        from ...demo.demo_llm import DemoLLM

        return DemoLLM()
    if settings.ai_provider != "gemini":
        raise MissingCredentials(f"Unsupported AI_PROVIDER '{settings.ai_provider}'. Supported: gemini.")
    return GeminiClient(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        timeout_seconds=settings.ai_timeout_seconds,
        max_retries=settings.ai_max_retries,
    )
