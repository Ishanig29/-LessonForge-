"""Instructor review of QC recommendations.

Applying a recommendation touches exactly one section: either the reviewer's
own replacement text is used, or the AI rewrites only that section. A new
lesson version records the change, and the previous section text is kept on
the recommendation so it can be undone safely (only if nobody has edited
that section since).
"""
from __future__ import annotations

import copy

from sqlalchemy.orm import Session

from ..models import Lesson, Recommendation
from ..models.entities import iso, utcnow
from ..prompts.templates import REVISION_PROMPT, REVISION_SYSTEM
from ..schemas.qc import SectionRevision
from ..utils.errors import Conflict, ValidationFailed
from .generation.evidence import evidence_pack
from .versions import create_version, current_version


def _target_section_id(rec: Recommendation, content: dict) -> str | None:
    section_ids = {s["id"] for s in content["sections"]}
    if rec.affected_section_id in section_ids:
        return rec.affected_section_id
    if rec.claim_key:
        claim = next((c for c in content.get("claims", []) if c["id"] == rec.claim_key), None)
        if claim and claim["section_id"] in section_ids:
            return claim["section_id"]
    return None


def apply_recommendation(session: Session, lesson: Lesson, rec: Recommendation, llm, use_ai: bool = True) -> dict:
    if rec.review_status == "accepted":
        raise Conflict("This recommendation has already been applied.")
    version = current_version(session, lesson)
    if version is None:
        raise ValidationFailed("Generate the lesson before applying recommendations.")
    content = copy.deepcopy(version.content)
    section_id = _target_section_id(rec, content)
    if section_id is None:
        raise ValidationFailed(
            "This recommendation does not target a single lesson section, so it cannot be applied "
            "automatically. Edit the lesson manually, then mark it as reviewed."
        )
    section = next(s for s in content["sections"] if s["id"] == section_id)
    previous = section["content"]

    if rec.suggested_text:
        new_text, summary, method = rec.suggested_text, "Applied reviewer's suggested text.", "suggested_text"
    elif use_ai:
        evidence, _ = evidence_pack(lesson, max_chars=12000)
        revision: SectionRevision = llm.generate_json(
            task="section_revision",
            system=REVISION_SYSTEM,
            prompt=REVISION_PROMPT.format(
                title=lesson.title, objective=lesson.learning_objective, section_id=section_id,
                kind=section["kind"], section_title=section["title"], content=previous,
                severity=rec.severity, issue=rec.issue, why=rec.why_it_matters or "",
                suggestion=rec.suggested_change, evidence=evidence,
            ),
            schema=SectionRevision,
            temperature=0.3,
        )
        new_text, summary, method = revision.content, revision.change_summary, "ai_section_rewrite"
    else:
        raise ValidationFailed("No replacement text is available for this recommendation.")

    section["content"] = new_text
    report = rec.report
    new_version = create_version(
        session, lesson, content, "recommendation",
        f"Applied {report.qc_type} recommendation {rec.issue_key} to section '{section['title']}': {summary}",
    )
    rec.review_status = "accepted"
    rec.applied_at = utcnow()
    rec.reviewed_at = utcnow()
    rec.applied_version_id = new_version.id
    rec.previous_section_content = previous
    rec.applied_section_content = new_text
    rec.affected_section_id = section_id
    if lesson.status in ("Finalized", "QC Reviewed"):
        lesson.status = "Generated"
    return {"version_number": new_version.version_number, "section_id": section_id, "method": method,
            "change_summary": summary}


def undo_recommendation(session: Session, lesson: Lesson, rec: Recommendation) -> dict:
    if rec.review_status != "accepted" or rec.previous_section_content is None:
        raise Conflict("Only applied recommendations can be undone.")
    version = current_version(session, lesson)
    content = copy.deepcopy(version.content)
    section = next((s for s in content["sections"] if s["id"] == rec.affected_section_id), None)
    if section is None:
        raise Conflict("The affected section no longer exists, so the change cannot be undone automatically.")
    if section["content"] != rec.applied_section_content:
        raise Conflict(
            "The section has been edited since this recommendation was applied. Undo would overwrite "
            "those edits, so it was not performed. Restore an earlier version from History instead."
        )
    section["content"] = rec.previous_section_content
    new_version = create_version(
        session, lesson, content, "undo", f"Undid recommendation {rec.issue_key} on section '{section['title']}'"
    )
    rec.review_status = "undone"
    rec.reviewed_at = utcnow()
    return {"version_number": new_version.version_number, "section_id": section["id"]}


def set_review_status(rec: Recommendation, status: str) -> None:
    if rec.review_status == "accepted" and status != "accepted":
        raise Conflict("Undo the applied change before changing this recommendation's status.")
    rec.review_status = status
    rec.reviewed_at = utcnow()


def serialize_recommendation(rec: Recommendation, stale: bool) -> dict:
    return {
        "id": rec.id, "qc_report_id": rec.qc_report_id, "qc_type": rec.report.qc_type,
        "report_version_number": rec.report.version_number, "report_stale": stale,
        "issue_key": rec.issue_key, "affected_section_id": rec.affected_section_id, "claim_key": rec.claim_key,
        "issue": rec.issue, "why_it_matters": rec.why_it_matters, "suggested_change": rec.suggested_change,
        "suggested_text": rec.suggested_text, "severity": rec.severity, "review_status": rec.review_status,
        "applied_at": iso(rec.applied_at), "reviewed_at": iso(rec.reviewed_at),
        "applied_version_id": rec.applied_version_id,
        "can_undo": rec.review_status == "accepted" and rec.previous_section_content is not None,
    }
