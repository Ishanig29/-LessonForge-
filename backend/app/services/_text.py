"""Tiny text helpers shared by services."""
from __future__ import annotations

import hashlib
import json
import re


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def content_hash(content: dict) -> str:
    """Canonical SHA-256 of a lesson document; drives stale-report detection."""
    canonical = json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def truncate(text: str | None, limit: int) -> str:
    text = text or ""
    return text if len(text) <= limit else text[: limit - 1] + "…"
