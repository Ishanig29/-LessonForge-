"""Research provider factory (overridable in tests; demo fixtures in demo mode)."""
from __future__ import annotations

from flask import current_app

_override: dict | None = None


def set_providers_override(providers: dict | None) -> None:
    global _override
    _override = providers


def get_providers() -> dict:
    if _override is not None:
        return _override
    settings = current_app.config["SETTINGS"]
    if settings.demo_mode:
        from ...demo.demo_research import demo_providers

        return demo_providers()
    from .orchestrator import make_providers

    return make_providers(settings)
