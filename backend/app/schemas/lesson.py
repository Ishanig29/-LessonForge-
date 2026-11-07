"""Pydantic schemas for user input and for the structured lesson document."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Difficulty = Literal["Beginner", "Intermediate", "Advanced"]
DeliveryMode = Literal["Self-learning", "Instructor-led"]

TITLE_MAX = 200
OBJECTIVE_MAX = 1000
AUDIENCE_MAX = 300
INSTRUCTIONS_MAX = 2000
SECTION_CONTENT_MAX = 20000


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    return re.sub(r"[ \t]+", " ", value).strip()


class LessonCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=TITLE_MAX)
    learning_objective: str = Field(min_length=10, max_length=OBJECTIVE_MAX)
    audience: str | None = Field(default=None, max_length=AUDIENCE_MAX)
    difficulty: Difficulty = "Beginner"
    delivery_mode: DeliveryMode = "Self-learning"
    additional_instructions: str | None = Field(default=None, max_length=INSTRUCTIONS_MAX)

    @field_validator("title", "learning_objective", "audience", "additional_instructions", mode="before")
    @classmethod
    def strip(cls, v):
        return _clean(v) if isinstance(v, str) else v

    @field_validator("audience", "additional_instructions")
    @classmethod
    def empty_to_none(cls, v):
        return v or None


class LessonMetaUpdate(BaseModel):
    """Editable lesson metadata (not the generated body)."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=3, max_length=TITLE_MAX)
    learning_objective: str | None = Field(default=None, min_length=10, max_length=OBJECTIVE_MAX)
    audience: str | None = Field(default=None, max_length=AUDIENCE_MAX)
    difficulty: Difficulty | None = None
    delivery_mode: DeliveryMode | None = None
    additional_instructions: str | None = Field(default=None, max_length=INSTRUCTIONS_MAX)

    @field_validator("title", "learning_objective", "audience", "additional_instructions", mode="before")
    @classmethod
    def strip(cls, v):
        return _clean(v) if isinstance(v, str) else v


# --------------------------------------------------------------------------
# Objective analysis
# --------------------------------------------------------------------------
class LearningOutcome(BaseModel):
    id: str = Field(pattern=r"^LO\d+$")
    outcome: str = Field(min_length=5)
    bloom_level: str
    measurable_by: str


class ObjectiveAnalysis(BaseModel):
    interpretation: str = Field(min_length=10)
    learners_should_understand: list[str] = Field(min_length=1)
    learners_should_be_able_to: list[str] = Field(min_length=1)
    key_concepts: list[str] = Field(min_length=1, max_length=12)
    expected_difficulty: str
    prerequisites: list[str] = Field(default_factory=list)
    assessment_methods: list[str] = Field(min_length=1)
    learning_outcomes: list[LearningOutcome] = Field(min_length=1, max_length=8)
    search_queries: list[str] = Field(min_length=1, max_length=8)


# --------------------------------------------------------------------------
# Lesson document
# --------------------------------------------------------------------------
SectionKind = Literal[
    "introduction",
    "prerequisites",
    "concept",
    "worked_example",
    "application",
    "activity",
    "knowledge_check",
    "answers",
    "takeaways",
    "summary",
]

# Every lesson must contain at least one section of each of these kinds.
REQUIRED_SECTION_KINDS: tuple[str, ...] = (
    "introduction",
    "concept",
    "worked_example",
    "application",
    "activity",
    "knowledge_check",
    "answers",
    "takeaways",
    "summary",
)


class LessonSection(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    kind: SectionKind
    title: str = Field(min_length=1, max_length=200)
    duration_minutes: int = Field(ge=0, le=45)
    activity: str = Field(default="", max_length=500, description="What the teacher/learner does")
    content: str = Field(default="", max_length=SECTION_CONTENT_MAX, description="Markdown body")


class KnowledgeCheckQuestion(BaseModel):
    id: str = Field(pattern=r"^Q\d+$")
    question: str = Field(min_length=5)
    kind: Literal["multiple_choice", "short_answer", "practical"] = "multiple_choice"
    options: list[str] = Field(default_factory=list)
    answer: str = Field(min_length=1)
    explanation: str = Field(min_length=5)
    outcome_ids: list[str] = Field(default_factory=list)


ClaimStatus = Literal[
    "Supported", "Partially Supported", "Unsupported", "Conflicting Evidence", "Unable to Verify"
]


class LessonClaim(BaseModel):
    id: str = Field(pattern=r"^C\d+$")
    text: str = Field(min_length=5)
    section_id: str
    source_ids: list[str] = Field(default_factory=list)
    evidence_excerpt: str | None = None
    # Filled by the backend verifier, never trusted from the model:
    status: ClaimStatus | None = None
    verification_note: str | None = None
    needs_research: bool = False


class LessonContent(BaseModel):
    """The full structured lesson as produced by generation and edited by instructors."""

    title: str = Field(min_length=3, max_length=TITLE_MAX)
    learning_objective: str = Field(min_length=10, max_length=OBJECTIVE_MAX)
    learning_outcomes: list[str] = Field(min_length=1)
    target_audience: str
    assumed_knowledge: str
    sections: list[LessonSection] = Field(min_length=1)
    knowledge_check: list[KnowledgeCheckQuestion] = Field(min_length=1)
    claims: list[LessonClaim] = Field(default_factory=list)
    # Populated by the backend from stored research sources (never generated text).
    supplementary_video_ids: list[str] = Field(default_factory=list)
    reference_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_structure(self):
        ids = [s.id for s in self.sections]
        if len(ids) != len(set(ids)):
            raise ValueError("Section ids must be unique")
        kinds = {s.kind for s in self.sections}
        missing = [k for k in REQUIRED_SECTION_KINDS if k not in kinds]
        if missing:
            raise ValueError(f"Lesson is missing required section kinds: {', '.join(missing)}")
        q_ids = [q.id for q in self.knowledge_check]
        if len(q_ids) != len(set(q_ids)):
            raise ValueError("Knowledge-check question ids must be unique")
        claim_ids = [c.id for c in self.claims]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("Claim ids must be unique")
        return self


class LessonContentUpdate(BaseModel):
    """Body for saving instructor edits."""

    model_config = ConfigDict(extra="forbid")

    content: LessonContent
    change_description: str = Field(default="Instructor edit", max_length=500)
    autosave: bool = False
    create_version: bool = False
