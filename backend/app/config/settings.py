"""Application settings loaded from environment variables.

Secrets (API keys) are read here and never serialised to the frontend;
`public_status()` only reports whether each key is *present*.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass
class Settings:
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'instance' / 'lessonforge.db'}"
        )
    )
    # AI provider ------------------------------------------------------------
    ai_provider: str = field(default_factory=lambda: os.getenv("AI_PROVIDER", "gemini"))
    gemini_api_key: str | None = field(default_factory=lambda: os.getenv("GEMINI_API_KEY") or None)
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.5-flash"))
    ai_timeout_seconds: int = field(default_factory=lambda: _int("AI_TIMEOUT_SECONDS", 180))
    ai_max_retries: int = field(default_factory=lambda: _int("AI_MAX_RETRIES", 2))
    # Research providers -----------------------------------------------------
    tavily_api_key: str | None = field(default_factory=lambda: os.getenv("TAVILY_API_KEY") or None)
    google_books_api_key: str | None = field(
        default_factory=lambda: os.getenv("GOOGLE_BOOKS_API_KEY") or None
    )
    youtube_api_key: str | None = field(default_factory=lambda: os.getenv("YOUTUBE_API_KEY") or None)
    http_timeout_seconds: int = field(default_factory=lambda: _int("HTTP_TIMEOUT_SECONDS", 25))
    # Behaviour --------------------------------------------------------------
    demo_mode: bool = field(default_factory=lambda: _bool("DEMO_MODE", False))
    cors_origins: str = field(
        default_factory=lambda: os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    )
    max_lesson_minutes: int = 45

    def public_status(self) -> dict:
        """Safe-to-expose configuration summary (no secret values)."""
        return {
            "ai_provider": self.ai_provider,
            "ai_model": self.gemini_model,
            "demo_mode": self.demo_mode,
            "max_lesson_minutes": self.max_lesson_minutes,
            "integrations": {
                "gemini": {"configured": bool(self.gemini_api_key), "env_var": "GEMINI_API_KEY"},
                "tavily": {"configured": bool(self.tavily_api_key), "env_var": "TAVILY_API_KEY"},
                "google_books": {
                    "configured": True,  # Google Books works without a key (lower quota)
                    "has_key": bool(self.google_books_api_key),
                    "env_var": "GOOGLE_BOOKS_API_KEY",
                    "note": "Optional: the public endpoint works without a key at a lower quota.",
                },
                "youtube": {"configured": bool(self.youtube_api_key), "env_var": "YOUTUBE_API_KEY"},
            },
        }
