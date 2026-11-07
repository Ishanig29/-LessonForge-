"""SQLAlchemy ORM entities.

Design notes
------------
* ``LessonVersion`` rows hold the full structured lesson as JSON. Every
  meaningful change produces a new row; the original generated version is
  never mutated.
* ``content_hash`` on versions and QC reports is what makes stale-report
  detection exact: a report is fresh only if it was produced for content
  whose hash equals the current version's hash.
* ``WorkflowExecution`` keeps one row per (lesson, step). Retrying a step
  updates the row and increments ``retry_count`` rather than piling up
  duplicates.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


LESSON_STATUSES = ("Draft", "Researching", "Generated", "QC Reviewed", "Finalized")
SOURCE_TYPES = ("website", "book", "youtube")
EVIDENCE_USE = ("evidence", "supplementary", "further_reading", "excluded")
EVIDENCE_STATUSES = (
    "Supported",
    "Partially Supported",
    "Unsupported",
    "Conflicting Evidence",
    "Unable to Verify",
)
SEVERITIES = ("Critical", "High", "Medium", "Low", "Informational")
STEP_STATUSES = ("Pending", "Running", "Completed", "Failed", "Retrying")


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    learning_objective: Mapped[str] = mapped_column(Text, nullable=False)
    audience: Mapped[str | None] = mapped_column(String(300))
    difficulty: Mapped[str] = mapped_column(String(20), default="Beginner", nullable=False)
    delivery_mode: Mapped[str] = mapped_column(String(30), default="Self-learning", nullable=False)
    additional_instructions: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="Draft", nullable=False)
    objective_analysis: Mapped[dict | None] = mapped_column(JSON)
    current_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("lesson_versions.id", use_alter=True, ondelete="SET NULL")
    )
    finalized_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("lesson_versions.id", use_alter=True, ondelete="SET NULL")
    )
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    versions: Mapped[list["LessonVersion"]] = relationship(
        back_populates="lesson",
        cascade="all, delete-orphan",
        foreign_keys="LessonVersion.lesson_id",
        order_by="LessonVersion.version_number",
        passive_deletes=True,
    )
    sources: Mapped[list["ResearchSource"]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan", passive_deletes=True
    )
    reports: Mapped[list["QCReport"]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan", passive_deletes=True
    )
    workflow_steps: Mapped[list["WorkflowExecution"]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan", passive_deletes=True
    )
    current_version: Mapped["LessonVersion | None"] = relationship(
        foreign_keys=[current_version_id], post_update=True
    )


class LessonVersion(Base):
    __tablename__ = "lesson_versions"
    __table_args__ = (UniqueConstraint("lesson_id", "version_number", name="uq_version_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # generated | regenerated | instructor_edit | recommendation | undo | restore
    origin: Mapped[str] = mapped_column(String(30), nullable=False, default="generated")
    change_description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    lesson: Mapped[Lesson] = relationship(back_populates="versions", foreign_keys=[lesson_id])
    claims: Mapped[list["Claim"]] = relationship(
        back_populates="version", cascade="all, delete-orphan", passive_deletes=True,
        order_by="Claim.id",
    )


class ResearchSource(Base):
    __tablename__ = "research_sources"
    __table_args__ = (
        UniqueConstraint("lesson_id", "source_key", name="uq_source_key"),
        UniqueConstraint("lesson_id", "dedupe_key", name="uq_source_dedupe"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)
    source_key: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. "S3"
    dedupe_key: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str | None] = mapped_column(String(1000))
    author_or_domain: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)  # retrieved text actually available as evidence
    extra: Mapped[dict | None] = mapped_column("metadata", JSON)
    published_date: Mapped[str | None] = mapped_column(String(40))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    query: Mapped[str | None] = mapped_column(String(500))
    reliability_score: Mapped[float] = mapped_column(Float, default=0.0)
    reliability_tier: Mapped[str] = mapped_column(String(40), default="unknown")
    reliability_rationale: Mapped[str | None] = mapped_column(Text)
    evidence_use: Mapped[str] = mapped_column(String(30), default="supplementary")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    lesson: Mapped[Lesson] = relationship(back_populates="sources")


class Claim(Base):
    __tablename__ = "claims"
    __table_args__ = (UniqueConstraint("lesson_version_id", "claim_key", name="uq_claim_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lesson_version_id: Mapped[int] = mapped_column(
        ForeignKey("lesson_versions.id", ondelete="CASCADE"), nullable=False
    )
    claim_key: Mapped[str] = mapped_column(String(20), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    section_id: Mapped[str] = mapped_column(String(80), nullable=False)
    source_keys: Mapped[list] = mapped_column(JSON, default=list)
    evidence_excerpt: Mapped[str | None] = mapped_column(Text)
    evidence_status: Mapped[str] = mapped_column(String(30), nullable=False)
    verification_note: Mapped[str | None] = mapped_column(Text)
    needs_research: Mapped[bool] = mapped_column(Boolean, default=False)

    version: Mapped[LessonVersion] = relationship(back_populates="claims")


class QCReport(Base):
    __tablename__ = "qc_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)
    lesson_version_id: Mapped[int | None] = mapped_column(
        ForeignKey("lesson_versions.id", ondelete="SET NULL")
    )
    version_number: Mapped[int | None] = mapped_column(Integer)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    qc_type: Mapped[str] = mapped_column(String(20), nullable=False)  # factual | instructional
    score: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # completed | failed
    report: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(80))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    lesson: Mapped[Lesson] = relationship(back_populates="reports")
    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="report", cascade="all, delete-orphan", passive_deletes=True,
        order_by="Recommendation.id",
    )


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    qc_report_id: Mapped[int] = mapped_column(ForeignKey("qc_reports.id", ondelete="CASCADE"), nullable=False)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)
    issue_key: Mapped[str] = mapped_column(String(30), nullable=False)
    affected_section_id: Mapped[str | None] = mapped_column(String(80))
    claim_key: Mapped[str | None] = mapped_column(String(20))
    issue: Mapped[str] = mapped_column(Text, nullable=False)
    why_it_matters: Mapped[str | None] = mapped_column(Text)
    suggested_change: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_text: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    # pending | accepted | rejected | reviewed | undone
    review_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applied_version_id: Mapped[int | None] = mapped_column(ForeignKey("lesson_versions.id", ondelete="SET NULL"))
    previous_section_content: Mapped[str | None] = mapped_column(Text)
    applied_section_content: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    report: Mapped[QCReport] = relationship(back_populates="recommendations")


class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"
    __table_args__ = (UniqueConstraint("lesson_id", "step_name", name="uq_step_per_lesson"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)
    step_name: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="Pending", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(40))
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    lesson: Mapped[Lesson] = relationship(back_populates="workflow_steps")
