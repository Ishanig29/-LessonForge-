"""Schemas and fixed rubrics for the two independent QC evaluators.

The model scores each rubric criterion; the *backend* clamps every criterion
to its maximum and sums them. The overall score is therefore traceable to
named criteria and cannot exceed the rubric, regardless of model output.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["Critical", "High", "Medium", "Low", "Informational"]

FACTUAL_RUBRIC: dict[str, tuple[int, str]] = {
    "factual_correctness": (35, "Statements, terminology and explanations are technically correct and not misleading."),
    "evidence_support": (25, "Major claims are backed by relevant retrieved evidence; citations match the claim."),
    "source_reliability": (15, "Evidence comes from authoritative sources; primary sources used where they exist."),
    "consistency": (10, "Numbers, definitions and examples agree across sections; no contradictions."),
    "research_completeness": (15, "Important facts for the objective are present and adequately evidenced."),
}

INSTRUCTIONAL_RUBRIC: dict[str, tuple[int, str]] = {
    "objective_alignment": (20, "Every learning outcome is taught and the lesson teaches what the objective asks."),
    "clarity_accessibility": (15, "Explanations are understandable for the stated audience; jargon is explained."),
    "structure_progression": (10, "Logical order, useful introduction, meaningful summary."),
    "examples_applications": (15, "Relevant, sufficiently detailed worked examples and real-world applications."),
    "engagement_activities": (10, "Learners are actively involved; activities build understanding."),
    "assessment_quality": (15, "Questions measure the objective; answers are correct and explained."),
    "timing_realism": (10, "Duration fits 45 minutes and per-section allocations are realistic."),
    "teaching_readiness": (5, "An instructor could teach it / a learner could complete it independently."),
}


class RubricScore(BaseModel):
    criterion: str
    score: float
    rationale: str


class QCIssue(BaseModel):
    id: str
    severity: Severity
    category: str
    section_id: str | None = None
    claim_id: str | None = None
    explanation: str
    evidence_or_reason: str
    suggested_improvement: str
    suggested_text: str | None = Field(
        default=None,
        description="Optional full replacement markdown for the affected section.",
    )


class ClaimReview(BaseModel):
    claim_id: str
    status: Literal["Supported", "Partially Supported", "Unsupported", "Conflicting Evidence", "Unable to Verify"]
    rationale: str


class SourceFinding(BaseModel):
    source_id: str
    authority: Literal["high", "medium", "low"]
    is_primary: bool
    relevant: bool
    note: str


class FactualQCOutput(BaseModel):
    overall_assessment: str
    rubric: list[RubricScore]
    claim_reviews: list[ClaimReview]
    source_findings: list[SourceFinding] = Field(default_factory=list)
    issues: list[QCIssue] = Field(default_factory=list)
    missing_important_facts: list[str] = Field(default_factory=list)
    suggested_additional_research: list[str] = Field(default_factory=list)


class AreaFinding(BaseModel):
    summary: str
    strengths: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)


class OutcomeCoverage(BaseModel):
    outcome: str
    covered: bool
    where: list[str] = Field(default_factory=list)
    note: str = ""


class InstructionalFindings(BaseModel):
    objective_alignment: AreaFinding
    clarity: AreaFinding
    structure: AreaFinding
    examples_and_activities: AreaFinding
    assessment: AreaFinding
    timing: AreaFinding
    teaching_readiness: AreaFinding


class InstructionalQCOutput(BaseModel):
    overall_assessment: str
    rubric: list[RubricScore]
    findings: InstructionalFindings
    outcome_coverage: list[OutcomeCoverage] = Field(default_factory=list)
    issues: list[QCIssue] = Field(default_factory=list)


class SectionRevision(BaseModel):
    """Output of a scoped single-section rewrite (applying a recommendation)."""

    content: str = Field(min_length=1)
    change_summary: str


class TimingRevision(BaseModel):
    """Output of the shortening pass: new durations (and optionally trimmed content)."""

    sections: list["TimingRevisionSection"]


class TimingRevisionSection(BaseModel):
    id: str
    duration_minutes: int = Field(ge=0, le=45)
    content: str | None = None


TimingRevision.model_rebuild()
