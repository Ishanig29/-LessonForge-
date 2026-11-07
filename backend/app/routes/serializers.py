"""JSON serialisers for API responses."""
from __future__ import annotations

from ..models import Lesson, ResearchSource
from ..models.entities import iso
from ..services.qc.common import is_stale, latest_reports, serialize_report
from ..services.timing.planner import analyze_timing
from ..services.versions import serialize_version
from ..services.workflow import serialize_steps


def serialize_source(s: ResearchSource, include_content: bool = True) -> dict:
    extra = s.extra or {}
    data = {
        "id": s.id, "source_id": s.source_key, "lesson_id": s.lesson_id, "source_type": s.source_type,
        "provider": s.provider, "title": s.title, "url": s.url, "author_or_domain": s.author_or_domain,
        "description": s.description, "published_date": s.published_date, "retrieved_at": iso(s.retrieved_at),
        "query": s.query, "reliability_score": s.reliability_score, "reliability_tier": s.reliability_tier,
        "reliability_rationale": s.reliability_rationale, "evidence_use": s.evidence_use,
        "has_retrieved_text": bool(s.content), "content_length": len(s.content or ""),
        "metadata": {k: v for k, v in extra.items() if k != "passages"}, "is_demo": s.is_demo,
        "passages": extra.get("passages") or [],
    }
    if include_content:
        data["content_excerpt"] = (s.content or "")[:3000] or None
    return data


def lesson_summary(lesson: Lesson, current) -> dict:
    reports = latest_reports(lesson)
    return {
        "id": lesson.id, "title": lesson.title, "learning_objective": lesson.learning_objective,
        "status": lesson.status, "difficulty": lesson.difficulty, "delivery_mode": lesson.delivery_mode,
        "audience": lesson.audience, "is_demo": lesson.is_demo,
        "created_at": iso(lesson.created_at), "updated_at": iso(lesson.updated_at),
        "current_version_number": current.version_number if current else None,
        "duration_minutes": current.duration_minutes if current else None,
        "qc": {
            k: ({"score": r.score, "stale": is_stale(r, current), "version_number": r.version_number} if r else None)
            for k, r in reports.items()
        },
        "source_count": len(lesson.sources),
    }


def lesson_detail(lesson: Lesson, current) -> dict:
    data = lesson_summary(lesson, current)
    reports = latest_reports(lesson)
    data.update({
        "additional_instructions": lesson.additional_instructions,
        "objective_analysis": lesson.objective_analysis,
        "current_version": serialize_version(current) if current else None,
        "finalized_version_id": lesson.finalized_version_id,
        "is_current_finalized": bool(current and lesson.finalized_version_id == current.id
                                     and lesson.status == "Finalized"),
        "timing": analyze_timing(current.content) if current else None,
        "workflow": serialize_steps(lesson),
        "latest_reports": {k: (serialize_report(r, current, full=False) if r else None) for k, r in reports.items()},
        "source_counts": {
            t: sum(1 for s in lesson.sources if s.source_type == t) for t in ("website", "book", "youtube")
        },
        "evidence_source_count": sum(1 for s in lesson.sources if s.evidence_use == "evidence"),
    })
    return data
