"""Per-step workflow tracking with honest statuses.

Each step has exactly one ``WorkflowExecution`` row per lesson. Starting a
step that previously failed puts it in ``Retrying`` and increments
``retry_count``. Statuses are only ever set from real backend outcomes.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Lesson, WorkflowExecution
from ..models.entities import utcnow
from ..utils.errors import AppError

log = logging.getLogger("lessonforge.workflow")

WORKFLOW_STEPS: list[tuple[str, str]] = [
    ("objective_analysis", "Objective analysis"),
    ("research", "Research"),
    ("source_evaluation", "Source evaluation"),
    ("evidence_extraction", "Evidence extraction"),
    ("lesson_generation", "Lesson generation"),
    ("timing_validation", "Timing validation"),
    ("qc_factual", "QC Layer 1 · Factual accuracy"),
    ("qc_instructional", "QC Layer 2 · Instructional quality"),
    ("instructor_review", "Instructor review"),
    ("finalization", "Finalization"),
    ("export", "Export"),
]
STEP_NAMES = {name for name, _ in WORKFLOW_STEPS}


def get_step(session: Session, lesson: Lesson, name: str) -> WorkflowExecution:
    step = session.scalar(
        select(WorkflowExecution).where(WorkflowExecution.lesson_id == lesson.id, WorkflowExecution.step_name == name)
    )
    if step is None:
        step = WorkflowExecution(lesson_id=lesson.id, step_name=name, status="Pending", retry_count=0)
        session.add(step)
        session.flush()
    return step


def start_step(session: Session, lesson: Lesson, name: str) -> WorkflowExecution:
    step = get_step(session, lesson, name)
    if step.status in ("Failed", "Completed"):
        step.retry_count += 1
    step.status = "Retrying" if step.status == "Failed" else "Running"
    step.error_message = None
    step.error_code = None
    step.started_at = utcnow()
    step.completed_at = None
    session.commit()
    log.info("workflow.start lesson=%s step=%s status=%s", lesson.id, name, step.status)
    return step


def complete_step(session: Session, step: WorkflowExecution, summary: dict | None = None) -> None:
    step.status = "Completed"
    step.summary = summary
    step.completed_at = utcnow()
    session.commit()


def fail_step(session: Session, lesson_id: int, name: str, exc: Exception) -> None:
    """Record a failure in a clean transaction (discarding the step's partial writes)."""
    session.rollback()
    step = session.scalar(
        select(WorkflowExecution).where(WorkflowExecution.lesson_id == lesson_id, WorkflowExecution.step_name == name)
    )
    if step is None:
        return
    step.status = "Failed"
    step.error_message = exc.message if isinstance(exc, AppError) else "Unexpected internal error. See server logs."
    step.error_code = exc.code if isinstance(exc, AppError) else "internal_error"
    step.completed_at = utcnow()
    session.commit()
    log.warning("workflow.failed lesson=%s step=%s code=%s", lesson_id, name, step.error_code)


def mark_completed(session: Session, lesson: Lesson, name: str, summary: dict | None = None) -> None:
    step = get_step(session, lesson, name)
    if step.started_at is None:
        step.started_at = utcnow()
    step.status = "Completed"
    step.summary = summary
    step.error_message = None
    step.completed_at = utcnow()


def serialize_steps(lesson: Lesson) -> list[dict]:
    from ..models.entities import iso

    by_name = {s.step_name: s for s in lesson.workflow_steps}
    out = []
    for name, label in WORKFLOW_STEPS:
        s = by_name.get(name)
        out.append({
            "name": name,
            "label": label,
            "status": s.status if s else "Pending",
            "error_message": s.error_message if s else None,
            "error_code": s.error_code if s else None,
            "retry_count": s.retry_count if s else 0,
            "summary": s.summary if s else None,
            "started_at": iso(s.started_at) if s else None,
            "completed_at": iso(s.completed_at) if s else None,
        })
    return out
