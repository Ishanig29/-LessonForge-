"""QC Layer 2 — instructional quality.

Independent of Layer 1: it never receives the factual report. Inputs are the
original objective, the objective decomposition, the lesson, the system-computed
section timings and the learner profile.
"""
from __future__ import annotations

import json

from ...models import Lesson, LessonVersion
from ...prompts.templates import INSTRUCTIONAL_PROMPT, INSTRUCTIONAL_SYSTEM
from ...schemas.qc import INSTRUCTIONAL_RUBRIC, InstructionalQCOutput
from .._text import truncate
from ..timing.planner import analyze_timing
from .common import score_rubric, severity_counts, sort_issues


def automated_checks(lesson: Lesson, content: dict, timing: dict) -> list[dict]:
    issues: list[dict] = []
    n = 0

    def add(**kw):
        nonlocal n
        n += 1
        issues.append({"id": f"AUTO-I{n}", "category": "automated_check", "claim_id": None,
                       "suggested_text": None, **kw})

    for problem in timing["issues"]:
        add(severity="Critical" if "exceeds" in problem else "Medium", section_id=None,
            explanation=problem, evidence_or_reason="Programmatic timing validation.",
            suggested_improvement="Adjust section durations so the total is at most 45 minutes.")
    outcomes = [o["id"] for o in (lesson.objective_analysis or {}).get("learning_outcomes", [])]
    assessed = {oid for q in content.get("knowledge_check", []) for oid in q.get("outcome_ids", [])}
    kc_section = next((s["id"] for s in content["sections"] if s["kind"] == "knowledge_check"), None)
    for oid in outcomes:
        if oid not in assessed:
            add(severity="High", section_id=kc_section,
                explanation=f"Learning outcome {oid} is not measured by any knowledge-check question.",
                evidence_or_reason="Outcome-to-question mapping check.",
                suggested_improvement=f"Add or adapt a question that measures {oid}.")
    for q in content.get("knowledge_check", []):
        if q.get("kind") == "multiple_choice" and len(q.get("options") or []) < 3:
            add(severity="Medium", section_id=kc_section,
                explanation=f"Multiple-choice question {q['id']} has fewer than three options.",
                evidence_or_reason="Assessment structure check.",
                suggested_improvement="Provide 3-4 plausible options.")
        if q.get("kind") == "multiple_choice" and q.get("options") and q.get("answer") not in q["options"] \
                and not any(q.get("answer", "").startswith(o[:1]) for o in q["options"]):
            add(severity="Low", section_id=kc_section,
                explanation=f"The answer for {q['id']} does not match any listed option exactly.",
                evidence_or_reason="Assessment structure check.",
                suggested_improvement="Make the answer text identical to the correct option.")
    return issues


def run_instructional_qc(lesson: Lesson, version: LessonVersion, llm) -> tuple[int, dict]:
    content = version.content
    timing = analyze_timing(content)
    auto_issues = automated_checks(lesson, content, timing)
    timings = "\n".join(
        f"- {s['id']} ({s['kind']}): {s['duration_minutes']} min — {s['activity']}" for s in timing["sections"]
    )
    lesson_payload = {
        "learning_outcomes": content["learning_outcomes"],
        "target_audience": content["target_audience"],
        "assumed_knowledge": content["assumed_knowledge"],
        "sections": [{"id": s["id"], "kind": s["kind"], "title": s["title"], "activity": s["activity"],
                      "content": s["content"]} for s in content["sections"]],
        "knowledge_check": content["knowledge_check"],
    }
    rubric_text = "\n".join(f"- {k} (max {m}): {d}" for k, (m, d) in INSTRUCTIONAL_RUBRIC.items())
    out: InstructionalQCOutput = llm.generate_json(
        task="qc_instructional",
        system=INSTRUCTIONAL_SYSTEM,
        prompt=INSTRUCTIONAL_PROMPT.format(
            title=lesson.title, objective=lesson.learning_objective,
            audience=lesson.audience or "general learners", difficulty=lesson.difficulty,
            delivery_mode=lesson.delivery_mode,
            analysis=json.dumps(lesson.objective_analysis or {}, ensure_ascii=False)[:8000],
            total=timing["total_minutes"], limit=timing["limit_minutes"], timings=timings,
            lesson=truncate(json.dumps(lesson_payload, ensure_ascii=False), 60000),
            rubric=rubric_text,
        ),
        schema=InstructionalQCOutput,
        temperature=0.2,
    )
    score, rubric_rows = score_rubric(out.rubric, INSTRUCTIONAL_RUBRIC)
    section_ids = {s["id"] for s in content["sections"]}
    issues = [i.model_dump() for i in out.issues]
    for i in issues:
        if i.get("section_id") not in section_ids:
            i["section_id"] = None
        i["origin"] = "evaluator"
    for i in auto_issues:
        i["origin"] = "automated"
    all_issues = sort_issues(auto_issues + issues)
    report = {
        "qc_type": "instructional",
        "title": "QC Layer 2 — Instructional Quality Review",
        "overall_assessment": out.overall_assessment,
        "score": score,
        "score_max": 100,
        "rubric": rubric_rows,
        "score_disclaimer": "An AI-generated score is an assessment of teaching quality, not a guarantee.",
        "findings": out.findings.model_dump(),
        "outcome_coverage": [o.model_dump() for o in out.outcome_coverage],
        "timing": {k: timing[k] for k in ("total_minutes", "limit_minutes", "compliant", "by_category", "issues")},
        "issues": all_issues,
        "severity_counts": severity_counts(all_issues),
    }
    return score, report
