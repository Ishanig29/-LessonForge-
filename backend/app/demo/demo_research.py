"""Offline demo research providers.

Web sources are real documentation text captured from the documents' public
GitHub repositories (see scripts/build_demo_fixtures.py); every source carries a
capture note and is flagged ``is_demo`` in the database and UI. No book or video
fixtures are shipped, because inventing catalogue entries or video IDs would be
fabrication; those providers report that they are unavailable in demo mode.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from ..utils.errors import AppError

FIXTURES = Path(__file__).parent / "fixtures"


def detect_topic(text: str) -> str | None:
    t = text.lower()
    if "http" in t:
        return "http"
    if "join" in t and "sql" in t or "join" in t:
        return "sql"
    return None


class DemoWebProvider:
    name = "tavily"
    source_type = "website"

    def search(self, query: str, max_results: int = 5):
        topic = detect_topic(query)
        if topic is None:
            raise AppError(
                "Offline demo mode only contains fixtures for the two demonstration topics "
                "(HTTP Requests and Responses; Introduction to SQL Joins). Disable DEMO_MODE to research other topics.",
                code="demo_topic_unavailable",
            )
        data = json.loads((FIXTURES / f"sources_{topic}.json").read_text())
        out = []
        for item in data[:max_results]:
            item = copy.deepcopy(item)
            item["query"] = query
            out.append(item)
        return out


class DemoUnavailableProvider:
    def __init__(self, name: str, source_type: str, label: str):
        self.name, self.source_type, self.label = name, source_type, label

    def search(self, query: str, max_results: int = 4):
        raise AppError(
            f"{self.label} search is not available in offline demo mode (no fixture data is shipped, "
            "to avoid presenting invented catalogue entries). Configure the API key and disable DEMO_MODE.",
            code="missing_credentials",
        )


def demo_providers() -> dict:
    return {
        "tavily": DemoWebProvider(),
        "google_books": DemoUnavailableProvider("google_books", "book", "Google Books"),
        "youtube": DemoUnavailableProvider("youtube", "youtube", "YouTube"),
    }
