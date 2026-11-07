"""Objective analysis and structured lesson generation."""
from __future__ import annotations

import json

from ...models import Lesson
from ...prompts.templates import (
    GENERATION_PROMPT,
    GENERATION_SYSTEM,
    OBJECTIVE_PROMPT,
    OBJECTIVE_SYSTEM,
)
from ...schemas.lesson import LessonContent, ObjectiveAnalysis
from .evidence import evidence_pack

MAX_VIDEOS = 4
MAX_FURTHER_READING_BOOKS = 4
CODE_TOPIC_HINTS = ("sql", "http", "python", "javascript", "code", "api", "program", "query", "html", "css")


def _request_fields(lesson: Lesson) -> dict:
    return {
        "title": lesson.title,
        "objective": lesson.learning_objective,
        "audience": lesson.audience or "General learners new to the topic",
        "difficulty": lesson.difficulty,
        "delivery_mode": lesson.delivery_mode,
        "instructions": lesson.additional_instructions or "None",
    }


def analyze_objective(lesson: Lesson, llm) -> dict:
    result = llm.generate_json(
        task="objective_analysis",
        system=OBJECTIVE_SYSTEM,
        prompt=OBJECTIVE_PROMPT.format(**_request_fields(lesson)),
        schema=ObjectiveAnalysis,
        temperature=0.2,
    )
    data = result.model_dump()
    # Keep the instructor's wording and the AI interpretation side by side.
    data["original_objective"] = lesson.learning_objective
    return data


def generate_lesson_content(lesson: Lesson, llm) -> dict:
    evidence, metadata_only = evidence_pack(lesson)
    fields = _request_fields(lesson)
    topic = f"{lesson.title} {lesson.learning_objective}".lower()
    instructor_led = lesson.delivery_mode == "Instructor-led"
    prompt = GENERATION_PROMPT.format(
        **fields,
        analysis=json.dumps(lesson.objective_analysis or {}, ensure_ascii=False)[:8000],
        evidence=evidence,
        metadata_only=metadata_only,
        actor="instructor and learners" if instructor_led else "learner",
        code_hint=" and code blocks with expected output" if any(h in topic for h in CODE_TOPIC_HINTS) else "",
        mode_hint=(
            "Write for an instructor-led session: include facilitator prompts, pair/group work and "
            "discussion questions in the activity fields." if instructor_led else
            "Write for self-learning: speak directly to the learner, include self-check pauses and "
            "self-paced exercise instructions."
        ),
    )
    result: LessonContent = llm.generate_json(
        task="lesson_generation", system=GENERATION_SYSTEM, prompt=prompt, schema=LessonContent, temperature=0.4
    )
    doc = result.model_dump()
    # The instructor's original title and objective are authoritative.
    doc["title"] = lesson.title
    doc["learning_objective"] = lesson.learning_objective
    # Server-side status fields are never trusted from model output.
    for claim in doc["claims"]:
        claim["status"] = None
        claim["verification_note"] = None
        claim["needs_research"] = False
    attach_resource_lists(lesson, doc)
    return doc


def attach_resource_lists(lesson: Lesson, doc: dict) -> None:
    """Build references and supplementary videos from stored sources only."""
    by_key = {s.source_key: s for s in lesson.sources}
    cited: list[str] = []
    for claim in doc.get("claims", []):
        for key in claim.get("source_ids", []):
            if key in by_key and key not in cited:
                cited.append(key)
    books = sorted(
        (s for s in lesson.sources if s.source_type == "book" and s.evidence_use != "excluded"),
        key=lambda s: -s.reliability_score,
    )[:MAX_FURTHER_READING_BOOKS]
    videos = sorted(
        (s for s in lesson.sources if s.source_type == "youtube" and s.evidence_use != "excluded"),
        key=lambda s: -s.reliability_score,
    )[:MAX_VIDEOS]
    doc["reference_ids"] = [k for k in cited if by_key[k].source_type == "website"] + [b.source_key for b in books]
    doc["supplementary_video_ids"] = [v.source_key for v in videos]
