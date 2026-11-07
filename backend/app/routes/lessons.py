"""Lesson CRUD, workflow stages, QC, recommendations, versions and export."""
from __future__ import annotations

import copy
import io
from datetime import timedelta

from flask import Blueprint, current_app, jsonify, request, send_file
from sqlalchemy import or_, select

from ..models import Lesson, LessonVersion, QCReport, Recommendation, get_session
from ..models.entities import utcnow
from ..schemas.lesson import LessonContentUpdate, LessonCreate, LessonMetaUpdate
from ..services.ai import get_llm
from ..services.export.package import build_export, export_warnings
from ..services.generation.evidence import run_evidence_extraction
from ..services.generation.lesson import analyze_objective, generate_lesson_content
from ..services.qc.common import is_stale, latest_reports, persist_report, serialize_report
from ..services.qc.factual import run_factual_qc
from ..services.qc.instructional import run_instructional_qc
from ..services.recommendations import (
    apply_recommendation,
    serialize_recommendation,
    set_review_status,
    undo_recommendation,
)
from ..services.research import get_providers
from ..services.research.orchestrator import run_research, topic_terms
from ..services.timing.planner import analyze_timing, enforce_time_limit
from ..services.versions import create_version, current_version, save_edit, serialize_version
from ..services.workflow import complete_step, fail_step, get_step, mark_completed, start_step
from ..utils.errors import Conflict, NotFound, TimingLimitExceeded, ValidationFailed
from .serializers import lesson_detail, lesson_summary, serialize_source

bp = Blueprint("lessons", __name__)
STEP_LOCK_SECONDS = 600  # a step marked Running longer than this is assumed abandoned
PROVIDER_LABELS = {"tavily": "Web research", "google_books": "Books", "youtube": "Videos"}
EDITED_ORIGINS = {"instructor_edit", "recommendation", "undo", "restore"}


# ------------------------------------------------------------------ helpers
def _json() -> dict:
    data = request.get_json(silent=True)
    if data is None:
        if request.data:
            raise ValidationFailed("Request body must be valid JSON.")
        return {}
    if not isinstance(data, dict):
        raise ValidationFailed("Request body must be a JSON object.")
    return data


def _lesson(session, lesson_id: int) -> Lesson:
    lesson = session.get(Lesson, lesson_id)
    if lesson is None:
        raise NotFound(f"Lesson {lesson_id} was not found.")
    return lesson


def _detail(session, lesson: Lesson):
    session.refresh(lesson)
    return lesson_detail(lesson, current_version(session, lesson))


def _guard_not_running(session, lesson: Lesson, name: str) -> None:
    step = get_step(session, lesson, name)
    if step.status in ("Running", "Retrying") and step.started_at:
        started = step.started_at if step.started_at.tzinfo else step.started_at.replace(tzinfo=utcnow().tzinfo)
        if utcnow() - started < timedelta(seconds=STEP_LOCK_SECONDS):
            raise Conflict(f"The '{name}' step is already running for this lesson.")


def _run_stage(session, lesson: Lesson, name: str, fn):
    """Run one workflow stage with status tracking; persist failure and re-raise."""
    _guard_not_running(session, lesson, name)
    step = start_step(session, lesson, name)
    try:
        summary = fn()
    except Exception as exc:
        fail_step(session, lesson.id, name, exc)
        raise
    complete_step(session, step, summary)
    return summary


def _is_demo() -> bool:
    return bool(current_app.config["SETTINGS"].demo_mode)


def _refresh_qc_status(session, lesson: Lesson) -> None:
    cur = current_version(session, lesson)
    reports = latest_reports(lesson)
    fresh = all(r is not None and not is_stale(r, cur) for r in reports.values())
    if fresh and lesson.status == "Generated":
        lesson.status = "QC Reviewed"


# ------------------------------------------------------------------ CRUD
@bp.post("/lessons")
def create_lesson():
    payload = LessonCreate.model_validate(_json())
    session = get_session()
    lesson = Lesson(**payload.model_dump(), status="Draft", is_demo=_is_demo())
    session.add(lesson)
    session.commit()
    return jsonify(_detail(session, lesson)), 201


@bp.get("/lessons")
def list_lessons():
    session = get_session()
    stmt = select(Lesson)
    q = (request.args.get("q") or "").strip()
    if q:
        like = f"%{q[:100]}%"
        stmt = stmt.where(or_(Lesson.title.ilike(like), Lesson.learning_objective.ilike(like)))
    status = request.args.get("status")
    if status:
        stmt = stmt.where(Lesson.status == status)
    limit = min(max(int(request.args.get("limit", 200) or 200), 1), 500)
    lessons = session.scalars(stmt.order_by(Lesson.updated_at.desc()).limit(limit)).all()
    return jsonify({"lessons": [lesson_summary(l, current_version(session, l)) for l in lessons]})


@bp.get("/lessons/<int:lesson_id>")
def get_lesson(lesson_id: int):
    session = get_session()
    return jsonify(_detail(session, _lesson(session, lesson_id)))


@bp.put("/lessons/<int:lesson_id>")
def update_lesson(lesson_id: int):
    payload = LessonMetaUpdate.model_validate(_json())
    session = get_session()
    lesson = _lesson(session, lesson_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if field in ("title", "learning_objective") and not value:
            raise ValidationFailed(f"{field.replace('_', ' ').capitalize()} cannot be empty.")
        setattr(lesson, field, value)
    lesson.updated_at = utcnow()
    session.commit()
    return jsonify(_detail(session, lesson))


@bp.delete("/lessons/<int:lesson_id>")
def delete_lesson(lesson_id: int):
    session = get_session()
    lesson = _lesson(session, lesson_id)
    lesson.current_version_id = None
    lesson.finalized_version_id = None
    session.flush()
    session.delete(lesson)
    session.commit()
    return jsonify({"deleted": lesson_id})


@bp.post("/lessons/<int:lesson_id>/duplicate")
def duplicate_lesson(lesson_id: int):
    session = get_session()
    src = _lesson(session, lesson_id)
    cur = current_version(session, src)
    copy_ = Lesson(
        title=f"{src.title} (copy)"[:200], learning_objective=src.learning_objective, audience=src.audience,
        difficulty=src.difficulty, delivery_mode=src.delivery_mode,
        additional_instructions=src.additional_instructions, objective_analysis=copy.deepcopy(src.objective_analysis),
        status="Generated" if cur else "Draft", is_demo=src.is_demo,
    )
    session.add(copy_)
    session.flush()
    from ..models import ResearchSource

    for s in src.sources:
        copy_.sources.append(ResearchSource(
            source_key=s.source_key, dedupe_key=s.dedupe_key, source_type=s.source_type, provider=s.provider,
            title=s.title, url=s.url, author_or_domain=s.author_or_domain, description=s.description,
            content=s.content, extra=copy.deepcopy(s.extra), published_date=s.published_date,
            retrieved_at=s.retrieved_at, query=s.query, reliability_score=s.reliability_score,
            reliability_tier=s.reliability_tier, reliability_rationale=s.reliability_rationale,
            evidence_use=s.evidence_use, is_demo=s.is_demo,
        ))
    session.flush()
    if cur:
        content = copy.deepcopy(cur.content)
        content["title"] = copy_.title
        create_version(session, copy_, content, "duplicate", f"Duplicated from lesson {src.id} v{cur.version_number}")
    session.commit()
    return jsonify(_detail(session, copy_)), 201


# ------------------------------------------------------------------ workflow stages
@bp.get("/lessons/<int:lesson_id>/workflow")
def workflow(lesson_id: int):
    session = get_session()
    return jsonify({"workflow": _detail(session, _lesson(session, lesson_id))["workflow"]})


@bp.post("/lessons/<int:lesson_id>/analyze-objective")
def analyze(lesson_id: int):
    session = get_session()
    lesson = _lesson(session, lesson_id)

    def stage():
        lesson.objective_analysis = analyze_objective(lesson, get_llm())
        session.commit()
        return {"outcomes": len(lesson.objective_analysis["learning_outcomes"]),
                "concepts": len(lesson.objective_analysis["key_concepts"])}

    _run_stage(session, lesson, "objective_analysis", stage)
    return jsonify(_detail(session, lesson))


@bp.post("/lessons/<int:lesson_id>/research")
def research(lesson_id: int):
    body = _json()
    only = body.get("providers")
    if only is not None and (not isinstance(only, list) or not set(only) <= {"tavily", "google_books", "youtube"}):
        raise ValidationFailed("providers must be a list containing tavily, google_books and/or youtube.")
    session = get_session()
    lesson = _lesson(session, lesson_id)
    _guard_not_running(session, lesson, "research")
    if lesson.status == "Draft":
        lesson.status = "Researching"
    step = start_step(session, lesson, "research")
    try:
        result = run_research(session, lesson, get_providers(), only=only, is_demo=_is_demo())
        session.commit()  # persist whatever was found, even if a provider failed
    except Exception as exc:
        fail_step(session, lesson.id, "research", exc)
        raise
    web = next((p for p in result["providers"] if p["provider"] == "tavily"), None)
    failed = [p for p in result["providers"] if p["status"] == "failed"]
    if web is not None and web["status"] == "failed" and not any(
            s.source_type == "website" for s in lesson.sources):
        step.status = "Failed"
        step.error_message = f"Web research failed: {web['error']} Book/video results (if any) were saved."
        step.error_code = web["error_code"]
        step.summary = result
        step.completed_at = utcnow()
    else:
        complete_step(session, step, result)
        # Completed overall, but surface any provider that failed as a warning.
        step.error_message = "\n".join(f"{PROVIDER_LABELS[p['provider']]}: {p['error']}" for p in failed) or None
    mark_completed(session, lesson, "source_evaluation", {
        "evaluated": len(lesson.sources),
        "evidence": sum(1 for s in lesson.sources if s.evidence_use == "evidence"),
        "supplementary": sum(1 for s in lesson.sources if s.evidence_use == "supplementary"),
        "further_reading": sum(1 for s in lesson.sources if s.evidence_use == "further_reading"),
        "excluded": sum(1 for s in lesson.sources if s.evidence_use == "excluded"),
    })
    session.commit()
    return jsonify({"research": result, "lesson": _detail(session, lesson)})


@bp.post("/lessons/<int:lesson_id>/generate")
def generate(lesson_id: int):
    body = _json()
    session = get_session()
    lesson = _lesson(session, lesson_id)
    if not lesson.objective_analysis:
        raise Conflict("Run the objective analysis before generating the lesson.")
    research_step = get_step(session, lesson, "research")
    if research_step.status == "Pending":
        raise Conflict("Run research before generating the lesson.")
    edited = any(v.origin in EDITED_ORIGINS for v in lesson.versions)
    if edited and not body.get("confirm_overwrite"):
        raise Conflict(
            "This lesson contains instructor edits. Regenerating creates a new version and replaces the "
            "current content (previous versions stay in History). Confirm to continue.",
            code="confirm_overwrite_required",
        )
    llm = get_llm()
    terms = topic_terms(lesson)

    def extraction():
        summary = run_evidence_extraction(lesson, terms)
        session.commit()
        return summary

    _run_stage(session, lesson, "evidence_extraction", extraction)

    generated: dict = {}

    def generation():
        generated["doc"] = generate_lesson_content(lesson, llm)
        return {"sections": len(generated["doc"]["sections"]), "claims": len(generated["doc"]["claims"]),
                "questions": len(generated["doc"]["knowledge_check"])}

    _run_stage(session, lesson, "lesson_generation", generation)

    timing_holder: dict = {}

    def timing():
        doc, report = enforce_time_limit(generated["doc"], llm)
        origin = "regenerated" if lesson.versions else "generated"
        version = create_version(session, lesson, doc, origin,
                                 "AI-generated lesson" if origin == "generated" else "Regenerated by AI")
        if lesson.status in ("Draft", "Researching", "QC Reviewed", "Finalized"):
            lesson.status = "Generated"
        session.commit()
        timing_holder.update(report=report, version=version.version_number)
        if not report["compliant"]:
            # The version is saved (work is preserved) but the step honestly fails.
            raise TimingLimitExceeded(report.get("error") or "; ".join(report["issues"]))
        return {"total_minutes": report["total_minutes"], "revision_rounds": len(report["revision_rounds"]),
                "version_number": version.version_number}

    _run_stage(session, lesson, "timing_validation", timing)
    return jsonify({"timing": timing_holder.get("report"), "lesson": _detail(session, lesson)})


@bp.post("/lessons/<int:lesson_id>/validate-timing")
def validate_timing(lesson_id: int):
    """Re-validate the current version; if over the limit, run the AI shortening loop."""
    session = get_session()
    lesson = _lesson(session, lesson_id)
    cur = current_version(session, lesson)
    if cur is None:
        raise Conflict("Generate the lesson first.")
    result: dict = {}

    def stage():
        report = analyze_timing(cur.content)
        if report["over_by"] > 0:
            doc, report = enforce_time_limit(copy.deepcopy(cur.content), get_llm())
            create_version(session, lesson, doc, "timing_revision", "AI shortened sections to fit 45 minutes")
            session.commit()
        result["report"] = report
        if not report["compliant"]:
            raise TimingLimitExceeded(report.get("error") or "; ".join(report["issues"]))
        return {"total_minutes": report["total_minutes"]}

    _run_stage(session, lesson, "timing_validation", stage)
    return jsonify({"timing": result["report"], "lesson": _detail(session, lesson)})


# ------------------------------------------------------------------ QC
def _run_qc(lesson_id: int, kind: str):
    session = get_session()
    lesson = _lesson(session, lesson_id)
    version = current_version(session, lesson)
    if version is None:
        raise Conflict("Generate the lesson before running quality checks.")
    step_name = f"qc_{kind}"
    holder: dict = {}

    def stage():
        llm = get_llm()
        runner = run_factual_qc if kind == "factual" else run_instructional_qc
        score, report = runner(lesson, version, llm)
        row = persist_report(session, lesson, version, kind, score, report, llm.model_name,
                             getattr(llm, "is_demo", False))
        session.flush()
        _refresh_qc_status(session, lesson)
        session.commit()
        holder["report"] = row
        return {"score": score, "report_id": row.id, "version_number": version.version_number,
                "issues": len(report["issues"])}

    _run_stage(session, lesson, step_name, stage)
    return jsonify({"report": serialize_report(holder["report"], version), "lesson": _detail(session, lesson)})


@bp.post("/lessons/<int:lesson_id>/qc/factual")
def qc_factual(lesson_id: int):
    return _run_qc(lesson_id, "factual")


@bp.post("/lessons/<int:lesson_id>/qc/instructional")
def qc_instructional(lesson_id: int):
    return _run_qc(lesson_id, "instructional")


@bp.get("/lessons/<int:lesson_id>/reports")
def list_reports(lesson_id: int):
    session = get_session()
    lesson = _lesson(session, lesson_id)
    cur = current_version(session, lesson)
    full = request.args.get("full", "true").lower() != "false"
    reports = sorted(lesson.reports, key=lambda r: r.id, reverse=True)
    latest = latest_reports(lesson)
    return jsonify({
        "reports": [serialize_report(r, cur, full=full) for r in reports],
        "latest": {k: (r.id if r else None) for k, r in latest.items()},
    })


@bp.get("/lessons/<int:lesson_id>/reports/<int:report_id>")
def get_report(lesson_id: int, report_id: int):
    session = get_session()
    lesson = _lesson(session, lesson_id)
    report = session.get(QCReport, report_id)
    if report is None or report.lesson_id != lesson.id:
        raise NotFound("Report not found.")
    return jsonify(serialize_report(report, current_version(session, lesson)))


# ------------------------------------------------------------------ sources & claims
@bp.get("/lessons/<int:lesson_id>/sources")
def lesson_sources(lesson_id: int):
    session = get_session()
    lesson = _lesson(session, lesson_id)
    srcs = sorted(lesson.sources, key=lambda s: int(s.source_key[1:]))
    return jsonify({"sources": [serialize_source(s) for s in srcs], "workflow_research": next(
        (st.summary for st in lesson.workflow_steps if st.step_name == "research"), None)})


@bp.get("/lessons/<int:lesson_id>/claims")
def lesson_claims(lesson_id: int):
    session = get_session()
    lesson = _lesson(session, lesson_id)
    cur = current_version(session, lesson)
    if cur is None:
        return jsonify({"claims": [], "qc_review": None})
    factual = latest_reports(lesson)["factual"]
    qc_by_claim = {}
    qc_meta = None
    if factual:
        qc_by_claim = {c["claim_id"]: c for c in factual.report.get("claims", [])}
        qc_meta = {"report_id": factual.id, "version_number": factual.version_number,
                   "stale": is_stale(factual, cur)}
    by_key = {s.source_key: s for s in lesson.sources}
    claims = []
    for c in cur.content.get("claims", []):
        q = qc_by_claim.get(c["id"])
        claims.append({**c, "sources": [
            {"source_id": k, "title": by_key[k].title, "url": by_key[k].url, "source_type": by_key[k].source_type,
             "reliability_tier": by_key[k].reliability_tier, "evidence_use": by_key[k].evidence_use}
            for k in c["source_ids"] if k in by_key],
            "qc_status": q["final_status"] if q else None, "qc_rationale": q["rationale"] if q else None})
    return jsonify({"claims": claims, "qc_review": qc_meta})


@bp.patch("/lessons/<int:lesson_id>/claims/<claim_id>")
def flag_claim(lesson_id: int, claim_id: str):
    body = _json()
    if "needs_research" not in body or not isinstance(body["needs_research"], bool):
        raise ValidationFailed("needs_research (boolean) is required.")
    session = get_session()
    lesson = _lesson(session, lesson_id)
    cur = current_version(session, lesson)
    if cur is None:
        raise Conflict("No lesson content yet.")
    content = copy.deepcopy(cur.content)
    claim = next((c for c in content["claims"] if c["id"] == claim_id), None)
    if claim is None:
        raise NotFound(f"Claim {claim_id} not found.")
    claim["needs_research"] = body["needs_research"]
    save_edit(session, lesson, content, f"Flagged {claim_id} as needing research" if body["needs_research"]
              else f"Cleared research flag on {claim_id}", autosave=True)
    session.commit()
    return jsonify(_detail(session, lesson))


# ------------------------------------------------------------------ content, versions
@bp.put("/lessons/<int:lesson_id>/content")
def save_content(lesson_id: int):
    payload = LessonContentUpdate.model_validate(_json())
    session = get_session()
    lesson = _lesson(session, lesson_id)
    if lesson.current_version_id is None:
        raise Conflict("Generate the lesson before editing its content.")
    version, action = save_edit(session, lesson, payload.content.model_dump(), payload.change_description,
                                autosave=payload.autosave, force_new=payload.create_version)
    if action != "unchanged":
        lesson.title = version.content["title"]
        lesson.learning_objective = version.content["learning_objective"]
        mark_completed(session, lesson, "instructor_review", {"last_action": "edit",
                                                              "version_number": version.version_number})
    session.commit()
    return jsonify({"action": action, "version": serialize_version(version, include_content=False),
                    "lesson": _detail(session, lesson)})


@bp.get("/lessons/<int:lesson_id>/versions")
def list_versions(lesson_id: int):
    session = get_session()
    lesson = _lesson(session, lesson_id)
    return jsonify({"current_version_id": lesson.current_version_id,
                    "finalized_version_id": lesson.finalized_version_id,
                    "versions": [serialize_version(v, include_content=False) for v in reversed(lesson.versions)]})


@bp.post("/lessons/<int:lesson_id>/versions")
def snapshot_version(lesson_id: int):
    """Explicitly save the given content (or the current content) as a new named version."""
    body = _json()
    session = get_session()
    lesson = _lesson(session, lesson_id)
    cur = current_version(session, lesson)
    if cur is None:
        raise Conflict("Generate the lesson first.")
    description = str(body.get("change_description") or "Saved version")[:500]
    content = body.get("content") or cur.content
    version = create_version(session, lesson, content, "instructor_edit", description)
    session.commit()
    return jsonify({"version": serialize_version(version, include_content=False),
                    "lesson": _detail(session, lesson)}), 201


@bp.get("/lessons/<int:lesson_id>/versions/<int:version_id>")
def get_version(lesson_id: int, version_id: int):
    session = get_session()
    lesson = _lesson(session, lesson_id)
    v = session.get(LessonVersion, version_id)
    if v is None or v.lesson_id != lesson.id:
        raise NotFound("Version not found.")
    return jsonify(serialize_version(v))


@bp.post("/lessons/<int:lesson_id>/versions/<int:version_id>/restore")
def restore_version(lesson_id: int, version_id: int):
    session = get_session()
    lesson = _lesson(session, lesson_id)
    v = session.get(LessonVersion, version_id)
    if v is None or v.lesson_id != lesson.id:
        raise NotFound("Version not found.")
    new = create_version(session, lesson, copy.deepcopy(v.content), "restore",
                         f"Restored content of version {v.version_number}")
    if lesson.status in ("Finalized", "QC Reviewed"):
        lesson.status = "Generated"
    session.commit()
    return jsonify({"version": serialize_version(new, include_content=False), "lesson": _detail(session, lesson)})


# ------------------------------------------------------------------ recommendations
def _rec(session, lesson: Lesson, rec_id: int) -> Recommendation:
    rec = session.get(Recommendation, rec_id)
    if rec is None or rec.lesson_id != lesson.id:
        raise NotFound("Recommendation not found.")
    return rec


@bp.get("/lessons/<int:lesson_id>/recommendations")
def list_recommendations(lesson_id: int):
    session = get_session()
    lesson = _lesson(session, lesson_id)
    cur = current_version(session, lesson)
    recs = session.scalars(select(Recommendation).where(Recommendation.lesson_id == lesson.id)
                           .order_by(Recommendation.id.desc())).all()
    latest_ids = {r.id for r in latest_reports(lesson).values() if r}
    return jsonify({"recommendations": [
        {**serialize_recommendation(r, is_stale(r.report, cur)), "from_latest_report": r.qc_report_id in latest_ids}
        for r in recs]})


def _after_review(session, lesson: Lesson) -> None:
    pending = session.scalars(select(Recommendation).where(
        Recommendation.lesson_id == lesson.id, Recommendation.review_status == "pending")).all()
    mark_completed(session, lesson, "instructor_review", {"pending_recommendations": len(pending)})


@bp.post("/lessons/<int:lesson_id>/recommendations/<int:rec_id>/apply")
def apply_rec(lesson_id: int, rec_id: int):
    session = get_session()
    lesson = _lesson(session, lesson_id)
    rec = _rec(session, lesson, rec_id)
    result = apply_recommendation(session, lesson, rec, get_llm() if not rec.suggested_text else None)
    _after_review(session, lesson)
    session.commit()
    return jsonify({"result": result, "recommendation": serialize_recommendation(rec, True),
                    "lesson": _detail(session, lesson)})


@bp.post("/lessons/<int:lesson_id>/recommendations/<int:rec_id>/reject")
def reject_rec(lesson_id: int, rec_id: int):
    session = get_session()
    lesson = _lesson(session, lesson_id)
    rec = _rec(session, lesson, rec_id)
    set_review_status(rec, "rejected")
    _after_review(session, lesson)
    session.commit()
    cur = current_version(session, lesson)
    return jsonify({"recommendation": serialize_recommendation(rec, is_stale(rec.report, cur))})


@bp.post("/lessons/<int:lesson_id>/recommendations/<int:rec_id>/review")
def review_rec(lesson_id: int, rec_id: int):
    session = get_session()
    lesson = _lesson(session, lesson_id)
    rec = _rec(session, lesson, rec_id)
    set_review_status(rec, "reviewed")
    _after_review(session, lesson)
    session.commit()
    cur = current_version(session, lesson)
    return jsonify({"recommendation": serialize_recommendation(rec, is_stale(rec.report, cur))})


@bp.post("/lessons/<int:lesson_id>/recommendations/<int:rec_id>/undo")
def undo_rec(lesson_id: int, rec_id: int):
    session = get_session()
    lesson = _lesson(session, lesson_id)
    rec = _rec(session, lesson, rec_id)
    result = undo_recommendation(session, lesson, rec)
    session.commit()
    return jsonify({"result": result, "recommendation": serialize_recommendation(rec, True),
                    "lesson": _detail(session, lesson)})


# ------------------------------------------------------------------ finalize & export
@bp.post("/lessons/<int:lesson_id>/finalize")
def finalize(lesson_id: int):
    body = _json()
    session = get_session()
    lesson = _lesson(session, lesson_id)
    cur = current_version(session, lesson)
    if cur is None:
        raise Conflict("Generate the lesson before finalizing.")
    timing = analyze_timing(cur.content)
    if not timing["compliant"]:
        raise ValidationFailed("The lesson cannot be finalized: " + "; ".join(timing["issues"]))
    reports = latest_reports(lesson)
    warnings = [w for w in export_warnings(lesson, cur, reports) if "not finalized" not in w]
    if warnings and not body.get("acknowledge_warnings"):
        raise Conflict("Finalizing with outstanding warnings requires confirmation.",
                       details={"warnings": warnings}, code="warnings_require_acknowledgement")
    lesson.finalized_version_id = cur.id
    lesson.status = "Finalized"
    mark_completed(session, lesson, "finalization", {"version_number": cur.version_number,
                                                     "acknowledged_warnings": warnings})
    session.commit()
    return jsonify(_detail(session, lesson))


@bp.get("/lessons/<int:lesson_id>/export/preflight")
def export_preflight(lesson_id: int):
    session = get_session()
    lesson = _lesson(session, lesson_id)
    cur = current_version(session, lesson)
    if cur is None:
        return jsonify({"ready": False, "warnings": ["There is no generated lesson to export yet."]})
    return jsonify({"ready": True, "version_number": cur.version_number,
                    "warnings": export_warnings(lesson, cur, latest_reports(lesson))})


@bp.post("/lessons/<int:lesson_id>/export")
def export(lesson_id: int):
    body = _json()
    fmt = body.get("format", "zip")
    session = get_session()
    lesson = _lesson(session, lesson_id)
    version = current_version(session, lesson)
    if body.get("version_id"):
        version = session.get(LessonVersion, int(body["version_id"]))
        if version is None or version.lesson_id != lesson.id:
            raise NotFound("Version not found.")
    data, filename, mime = build_export(lesson, version, fmt)
    mark_completed(session, lesson, "export", {"format": fmt, "version_number": version.version_number,
                                               "filename": filename})
    session.commit()
    return send_file(io.BytesIO(data), mimetype=mime, as_attachment=True, download_name=filename)
