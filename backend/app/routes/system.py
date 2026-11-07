"""Health, configuration status and the cross-lesson research library."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import func, or_, select, text

from ..models import Lesson, ResearchSource, get_session
from ..models.entities import LESSON_STATUSES
from .serializers import serialize_source

bp = Blueprint("system", __name__)


@bp.get("/health")
def health():
    session = get_session()
    try:
        session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    settings = current_app.config["SETTINGS"]
    return jsonify({"status": "ok" if db_ok else "degraded", "database": "ok" if db_ok else "unavailable",
                    "config": settings.public_status()}), (200 if db_ok else 503)


@bp.get("/settings")
def settings_status():
    return jsonify(current_app.config["SETTINGS"].public_status())


@bp.get("/stats")
def stats():
    session = get_session()
    rows = session.execute(select(Lesson.status, func.count(Lesson.id)).group_by(Lesson.status)).all()
    by_status = {s: 0 for s in LESSON_STATUSES}
    by_status.update({s: n for s, n in rows})
    source_rows = session.execute(
        select(ResearchSource.source_type, func.count(ResearchSource.id)).group_by(ResearchSource.source_type)
    ).all()
    return jsonify({
        "lessons_total": sum(by_status.values()),
        "lessons_by_status": by_status,
        "sources_by_type": {t: n for t, n in source_rows},
    })


@bp.get("/sources")
def research_library():
    session = get_session()
    stmt = select(ResearchSource, Lesson.title).join(Lesson, Lesson.id == ResearchSource.lesson_id)
    stype = request.args.get("type")
    if stype in ("website", "book", "youtube"):
        stmt = stmt.where(ResearchSource.source_type == stype)
    use = request.args.get("evidence_use")
    if use:
        stmt = stmt.where(ResearchSource.evidence_use == use)
    q = (request.args.get("q") or "").strip()
    if q:
        like = f"%{q[:100]}%"
        stmt = stmt.where(or_(ResearchSource.title.ilike(like), ResearchSource.author_or_domain.ilike(like),
                              Lesson.title.ilike(like)))
    stmt = stmt.order_by(ResearchSource.retrieved_at.desc()).limit(500)
    out = []
    for src, lesson_title in session.execute(stmt).all():
        data = serialize_source(src, include_content=False)
        data["lesson_title"] = lesson_title
        out.append(data)
    return jsonify({"sources": out})
