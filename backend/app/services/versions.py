"""Lesson version management.

Rules:
* The generated version and every recommendation/undo/restore produce new,
  immutable rows.
* Autosaves are coalesced into the current version only if that version is an
  instructor edit, is recent, and no QC report has been produced for it. This
  keeps history meaningful without creating a version per keystroke.
* Claims are re-verified on every save, so evidence statuses always describe
  the content they sit next to.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Claim, Lesson, LessonVersion, QCReport, ResearchSource
from ..models.entities import utcnow
from ..schemas.lesson import LessonContent
from ..utils.errors import ValidationFailed
from ._text import content_hash
from .generation.evidence import verify_claims
from .timing.planner import analyze_timing

AUTOSAVE_COALESCE_WINDOW = timedelta(minutes=30)


def sources_by_key(lesson: Lesson) -> dict[str, ResearchSource]:
    return {s.source_key: s for s in lesson.sources}


def prepare_content(lesson: Lesson, content: dict) -> dict:
    """Validate the document, re-verify claims and drop references to unknown sources."""
    try:
        doc = LessonContent.model_validate(content).model_dump()
    except Exception as exc:  # pydantic ValidationError
        raise ValidationFailed("The lesson content is not valid.", details=_errors(exc)) from exc
    by_key = sources_by_key(lesson)
    section_ids = {s["id"] for s in doc["sections"]}
    for claim in doc["claims"]:
        if claim["section_id"] not in section_ids:
            claim["section_id"] = doc["sections"][0]["id"]
    doc["claims"] = verify_claims(doc["claims"], by_key)
    doc["reference_ids"] = [k for k in doc["reference_ids"] if k in by_key]
    doc["supplementary_video_ids"] = [
        k for k in doc["supplementary_video_ids"] if k in by_key and by_key[k].source_type == "youtube"
    ]
    return doc


def _errors(exc) -> list:
    try:
        return [{"loc": ".".join(map(str, e["loc"])), "msg": e["msg"]} for e in exc.errors()][:20]
    except Exception:
        return [str(exc)]


def _write_claims(session: Session, version: LessonVersion, doc: dict) -> None:
    for old in list(version.claims):
        session.delete(old)
    session.flush()
    for c in doc["claims"]:
        version.claims.append(Claim(
            claim_key=c["id"], text=c["text"], section_id=c["section_id"], source_keys=c["source_ids"],
            evidence_excerpt=c.get("evidence_excerpt"), evidence_status=c["status"],
            verification_note=c.get("verification_note"), needs_research=bool(c.get("needs_research")),
        ))


def create_version(session: Session, lesson: Lesson, content: dict, origin: str, description: str) -> LessonVersion:
    doc = prepare_content(lesson, content)
    number = (session.scalar(select(func.max(LessonVersion.version_number)).where(
        LessonVersion.lesson_id == lesson.id)) or 0) + 1
    timing = analyze_timing(doc)
    version = LessonVersion(
        lesson_id=lesson.id, version_number=number, content=doc, content_hash=content_hash(doc),
        duration_minutes=timing["total_minutes"], origin=origin, change_description=description[:500],
    )
    session.add(version)
    session.flush()
    _write_claims(session, version, doc)
    lesson.current_version_id = version.id
    lesson.updated_at = utcnow()
    return version


def current_version(session: Session, lesson: Lesson) -> LessonVersion | None:
    if lesson.current_version_id is None:
        return None
    return session.get(LessonVersion, lesson.current_version_id)


def save_edit(session: Session, lesson: Lesson, content: dict, description: str, autosave: bool,
              force_new: bool = False) -> tuple[LessonVersion, str]:
    """Save instructor edits. Returns (version, action) where action is
    'unchanged' | 'updated' | 'created'."""
    cur = current_version(session, lesson)
    doc = prepare_content(lesson, content)
    new_hash = content_hash(doc)
    if cur is not None and cur.content_hash == new_hash and not force_new:
        return cur, "unchanged"
    if cur is not None and autosave and not force_new and _can_coalesce(session, cur):
        cur.content = doc
        cur.content_hash = new_hash
        cur.duration_minutes = analyze_timing(doc)["total_minutes"]
        cur.updated_at = utcnow()
        _write_claims(session, cur, doc)
        lesson.updated_at = utcnow()
        _after_edit(lesson)
        return cur, "updated"
    version = create_version(session, lesson, doc, "instructor_edit", description or "Instructor edit")
    _after_edit(lesson)
    return version, "created"


def _can_coalesce(session: Session, version: LessonVersion) -> bool:
    if version.origin != "instructor_edit":
        return False
    created = version.created_at if version.created_at.tzinfo else version.created_at.replace(tzinfo=utcnow().tzinfo)
    if utcnow() - created > AUTOSAVE_COALESCE_WINDOW:
        return False
    has_report = session.scalar(select(func.count(QCReport.id)).where(QCReport.lesson_version_id == version.id))
    return not has_report


def _after_edit(lesson: Lesson) -> None:
    # Edited content is no longer the finalized or QC-reviewed artefact.
    if lesson.status in ("Finalized", "QC Reviewed"):
        lesson.status = "Generated"


def serialize_version(v: LessonVersion, include_content: bool = True) -> dict:
    from ..models.entities import iso

    data = {
        "id": v.id, "version_number": v.version_number, "origin": v.origin,
        "change_description": v.change_description, "duration_minutes": v.duration_minutes,
        "content_hash": v.content_hash, "created_at": iso(v.created_at), "updated_at": iso(v.updated_at),
    }
    if include_content:
        data["content"] = v.content
    return data
