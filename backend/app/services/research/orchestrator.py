"""Runs the three research providers independently and persists results.

* A failure in one provider never discards results from another.
* Re-running research merges into existing sources by ``dedupe_key`` so
  source IDs (S1, S2, …) stay stable for claims that already cite them.
"""
from __future__ import annotations

import logging
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import Lesson, ResearchSource
from ...utils.errors import AppError
from .evaluation import dedupe, dedupe_key, evaluate, tokenize
from .providers import GoogleBooksProvider, RawSource, TavilyProvider, YouTubeProvider

log = logging.getLogger("lessonforge.research")

PROVIDER_ORDER = ("tavily", "google_books", "youtube")
MAX_WEB_QUERIES, WEB_RESULTS = 4, 5
MAX_BOOK_QUERIES, BOOK_RESULTS = 2, 4
MAX_VIDEO_QUERIES, VIDEO_RESULTS = 2, 4


def build_queries(lesson: Lesson) -> dict[str, list[str]]:
    analysis = lesson.objective_analysis or {}
    ai_queries = [q for q in analysis.get("search_queries", []) if isinstance(q, str) and q.strip()]
    base = [lesson.title, f"{lesson.title} {lesson.learning_objective[:120]}"]
    web = list(dict.fromkeys(ai_queries + base))[:MAX_WEB_QUERIES]
    concepts = analysis.get("key_concepts") or []
    books = list(dict.fromkeys([lesson.title] + ([" ".join(concepts[:3])] if concepts else [])))[:MAX_BOOK_QUERIES]
    videos = list(dict.fromkeys([f"{lesson.title} explained", f"{lesson.title} tutorial"]))[:MAX_VIDEO_QUERIES]
    return {"tavily": web, "google_books": books, "youtube": videos}


def topic_terms(lesson: Lesson) -> set[str]:
    analysis = lesson.objective_analysis or {}
    return tokenize(" ".join([lesson.title, lesson.learning_objective, " ".join(analysis.get("key_concepts") or [])]))


def make_providers(settings) -> dict:
    t = settings.http_timeout_seconds
    return {
        "tavily": TavilyProvider(settings.tavily_api_key, t),
        "google_books": GoogleBooksProvider(settings.google_books_api_key, t),
        "youtube": YouTubeProvider(settings.youtube_api_key, t),
    }


def _next_key_number(session: Session, lesson_id: int) -> int:
    keys = session.scalars(select(ResearchSource.source_key).where(ResearchSource.lesson_id == lesson_id)).all()
    nums = [int(m.group(1)) for k in keys if (m := re.fullmatch(r"S(\d+)", k))]
    return max(nums, default=0) + 1


def run_research(session: Session, lesson: Lesson, providers: dict, only: list[str] | None = None,
                 is_demo: bool = False) -> dict:
    """Execute providers, persist new sources, and return a per-provider report."""
    queries = build_queries(lesson)
    terms = topic_terms(lesson)
    limits = {"tavily": WEB_RESULTS, "google_books": BOOK_RESULTS, "youtube": VIDEO_RESULTS}
    provider_reports: list[dict] = []
    collected: list[RawSource] = []

    for name in PROVIDER_ORDER:
        if only and name not in only:
            continue
        provider = providers[name]
        report = {"provider": name, "source_type": provider.source_type, "queries": queries[name],
                  "status": "ok", "found": 0, "error": None, "error_code": None}
        found: list[RawSource] = []
        errors: list[AppError] = []
        for q in queries[name]:
            try:
                found.extend(provider.search(q, limits[name]))
            except AppError as exc:
                errors.append(exc)
                if exc.code in ("missing_credentials", "invalid_credentials"):
                    break  # every further query would fail identically
        report["found"] = len(found)
        if errors and not found:
            report.update(status="failed", error=errors[0].message, error_code=errors[0].code)
        elif errors:
            report.update(status="partial", error=errors[0].message, error_code=errors[0].code)
        elif not found:
            report["status"] = "empty"
        provider_reports.append(report)
        collected.extend(found)
        log.info("research.provider name=%s status=%s found=%s", name, report["status"], len(found))

    unique = dedupe(collected)
    existing = {s.dedupe_key: s for s in lesson.sources}
    next_num = _next_key_number(session, lesson.id)
    added = updated = 0
    for raw in unique:
        key = dedupe_key(raw)
        ev = evaluate(raw, terms)
        if key in existing:
            src = existing[key]
            # Refresh content only if the new retrieval has more text.
            if len(raw.get("content") or "") > len(src.content or ""):
                src.content = raw.get("content")
                updated += 1
            src.reliability_score = ev["reliability_score"]
            src.reliability_rationale = ev["reliability_rationale"]
            src.reliability_tier = ev["reliability_tier"]
            src.evidence_use = ev["evidence_use"]
            continue
        src = ResearchSource(
            lesson_id=lesson.id,
            source_key=f"S{next_num}",
            dedupe_key=key,
            source_type=raw["source_type"],
            provider=raw["provider"],
            title=raw["title"],
            url=raw.get("url"),
            author_or_domain=raw.get("author_or_domain"),
            description=raw.get("description"),
            content=raw.get("content"),
            extra={**(raw.get("metadata") or {}), "relevance": ev["relevance"]},
            published_date=raw.get("published_date"),
            query=raw.get("query"),
            reliability_score=ev["reliability_score"],
            reliability_tier=ev["reliability_tier"],
            reliability_rationale=ev["reliability_rationale"],
            evidence_use=ev["evidence_use"],
            is_demo=is_demo,
        )
        session.add(src)
        lesson.sources.append(src)
        existing[key] = src
        next_num += 1
        added += 1

    duplicates_removed = len(collected) - len(unique)
    return {
        "providers": provider_reports,
        "added": added,
        "updated": updated,
        "duplicates_removed": duplicates_removed,
        "total_sources": len(lesson.sources),
        "evidence_sources": sum(1 for s in lesson.sources if s.evidence_use == "evidence"),
    }
