"""Helpers shared by both QC layers (scoring, persistence, freshness).

Only mechanical helpers live here; each layer's prompt, inputs, automated
checks and report format are defined in its own module.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ...models import Lesson, LessonVersion, QCReport, Recommendation
from ...models.entities import iso
from ...schemas.qc import RubricScore

SEVERITY_ORDER = ["Critical", "High", "Medium", "Low", "Informational"]


def score_rubric(items: list[RubricScore], rubric: dict[str, tuple[int, str]]) -> tuple[int, list[dict]]:
    """Clamp each criterion to its max and sum. Missing criteria score 0 and are flagged."""
    by_name = {i.criterion.strip().lower(): i for i in items}
    rows, total = [], 0.0
    for name, (maximum, description) in rubric.items():
        item = by_name.get(name)
        if item is None:
            rows.append({"criterion": name, "description": description, "max": maximum, "score": 0,
                         "rationale": "Evaluator did not score this criterion; counted as 0."})
            continue
        score = max(0.0, min(float(item.score), float(maximum)))
        total += score
        rows.append({"criterion": name, "description": description, "max": maximum,
                     "score": round(score, 1), "rationale": item.rationale})
    return int(round(total)), rows


def severity_counts(issues: list[dict]) -> dict[str, int]:
    counts = {s: 0 for s in SEVERITY_ORDER}
    for i in issues:
        counts[i["severity"]] = counts.get(i["severity"], 0) + 1
    return counts


def sort_issues(issues: list[dict]) -> list[dict]:
    return sorted(issues, key=lambda i: SEVERITY_ORDER.index(i["severity"]))


def persist_report(session: Session, lesson: Lesson, version: LessonVersion, qc_type: str, score: int,
                   report: dict, model: str, is_demo: bool) -> QCReport:
    row = QCReport(
        lesson_id=lesson.id, lesson_version_id=version.id, version_number=version.version_number,
        content_hash=version.content_hash, qc_type=qc_type, score=score, status="completed",
        report=report, model=model, is_demo=is_demo,
    )
    session.add(row)
    session.flush()
    for issue in report["issues"]:
        if issue["severity"] == "Informational" and not issue.get("suggested_text"):
            continue  # informational notes stay in the report; nothing to accept/reject
        row.recommendations.append(Recommendation(
            lesson_id=lesson.id,
            issue_key=issue["id"],
            affected_section_id=issue.get("section_id"),
            claim_key=issue.get("claim_id"),
            issue=issue["explanation"],
            why_it_matters=issue.get("evidence_or_reason"),
            suggested_change=issue["suggested_improvement"],
            suggested_text=issue.get("suggested_text"),
            severity=issue["severity"],
        ))
    return row


def is_stale(report: QCReport, current: LessonVersion | None) -> bool:
    return current is None or report.content_hash != current.content_hash


def serialize_report(report: QCReport, current: LessonVersion | None, full: bool = True) -> dict:
    stale = is_stale(report, current)
    data = {
        "id": report.id,
        "qc_type": report.qc_type,
        "score": report.score,
        "status": report.status,
        "version_number": report.version_number,
        "lesson_version_id": report.lesson_version_id,
        "model": report.model,
        "is_demo": report.is_demo,
        "created_at": iso(report.created_at),
        "stale": stale,
        "stale_reason": (
            f"The lesson changed after this report was produced for version {report.version_number}. "
            "Rerun this check to evaluate the current content." if stale else None
        ),
    }
    if full:
        data["report"] = report.report
    return data


def latest_reports(lesson: Lesson) -> dict[str, QCReport | None]:
    latest: dict[str, QCReport | None] = {"factual": None, "instructional": None}
    for r in sorted(lesson.reports, key=lambda r: r.id):
        if r.status == "completed":
            latest[r.qc_type] = r
    return latest
