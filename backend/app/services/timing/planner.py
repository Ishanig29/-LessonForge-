"""45-minute lesson planner.

The limit is enforced here in code, not by trusting the model:

* ``analyze_timing`` sums section durations and checks minimums.
* ``enforce_time_limit`` asks the AI to shorten an over-long lesson, applies
  only the changed sections, recomputes and re-validates — at most
  ``MAX_REVISION_ROUNDS`` times. If the lesson is still too long the result is
  reported as non-compliant; it is never marked compliant falsely.
"""
from __future__ import annotations

import json
import logging

from ...prompts.templates import TIMING_PROMPT, TIMING_SYSTEM
from ...schemas.qc import TimingRevision

log = logging.getLogger("lessonforge.timing")

MAX_LESSON_MINUTES = 45
MAX_REVISION_ROUNDS = 2
# Sections that must take real time (explanations, examples, activities, checks, summary).
MIN_ONE_MINUTE_KINDS = {"introduction", "concept", "worked_example", "activity", "knowledge_check", "summary"}
CATEGORY_OF_KIND = {
    "introduction": "Explanations",
    "prerequisites": "Explanations",
    "concept": "Explanations",
    "worked_example": "Examples",
    "application": "Examples",
    "activity": "Activities",
    "knowledge_check": "Knowledge checks",
    "answers": "Knowledge checks",
    "takeaways": "Summary",
    "summary": "Summary",
}


def analyze_timing(content: dict, limit: int = MAX_LESSON_MINUTES) -> dict:
    sections = content.get("sections", [])
    total = sum(int(s.get("duration_minutes") or 0) for s in sections)
    issues: list[str] = []
    for s in sections:
        if s.get("kind") in MIN_ONE_MINUTE_KINDS and int(s.get("duration_minutes") or 0) < 1:
            issues.append(f"Section '{s.get('title')}' ({s.get('kind')}) has no time allocated.")
    if total > limit:
        issues.append(f"Total duration {total} min exceeds the {limit}-minute limit by {total - limit} min.")
    if total == 0:
        issues.append("No time has been allocated to any section.")
    categories: dict[str, int] = {}
    for s in sections:
        cat = CATEGORY_OF_KIND.get(s.get("kind"), "Other")
        categories[cat] = categories.get(cat, 0) + int(s.get("duration_minutes") or 0)
    longest = sorted(sections, key=lambda s: -int(s.get("duration_minutes") or 0))[:3]
    return {
        "total_minutes": total,
        "limit_minutes": limit,
        "compliant": total <= limit and total > 0 and not any("no time" in i for i in issues),
        "over_by": max(0, total - limit),
        "issues": issues,
        "by_category": categories,
        "sections": [
            {"id": s.get("id"), "title": s.get("title"), "kind": s.get("kind"),
             "duration_minutes": int(s.get("duration_minutes") or 0), "activity": s.get("activity", "")}
            for s in sections
        ],
        "longest_sections": [s.get("id") for s in longest],
    }


def enforce_time_limit(content: dict, llm, limit: int = MAX_LESSON_MINUTES) -> tuple[dict, dict]:
    """Return (possibly revised content, timing report with revision history)."""
    history: list[dict] = []
    report = analyze_timing(content, limit)
    rounds = 0
    while report["over_by"] > 0 and rounds < MAX_REVISION_ROUNDS:
        rounds += 1
        sections = content["sections"]
        table = "\n".join(
            f"- {s['id']} ({s['kind']}): {s['duration_minutes']} min, {len(s.get('content', ''))} chars"
            for s in sections
        )
        contents = json.dumps(
            [{"id": s["id"], "content": s.get("content", "")} for s in sections if s["id"] in report["longest_sections"]],
            ensure_ascii=False,
        )
        revision = llm.generate_json(
            task="timing_revision",
            system=TIMING_SYSTEM,
            prompt=TIMING_PROMPT.format(
                total=report["total_minutes"], limit=limit, over=report["over_by"],
                longest=", ".join(report["longest_sections"]), table=table, contents=contents,
            ),
            schema=TimingRevision,
            temperature=0.2,
        )
        by_id = {s["id"]: s for s in sections}
        changed = []
        for rs in revision.sections:
            target = by_id.get(rs.id)
            if not target:
                continue  # ignore ids the model invented
            new_minutes = rs.duration_minutes
            if target["kind"] in MIN_ONE_MINUTE_KINDS:
                new_minutes = max(1, new_minutes)
            changed.append({"id": rs.id, "from": target["duration_minutes"], "to": new_minutes})
            target["duration_minutes"] = new_minutes
            if rs.content:
                target["content"] = rs.content
        before = report["total_minutes"]
        report = analyze_timing(content, limit)
        history.append({"round": rounds, "before": before, "after": report["total_minutes"], "changes": changed})
        log.info("timing.revision round=%s before=%s after=%s", rounds, before, report["total_minutes"])
    report["revision_rounds"] = history
    if report["over_by"] > 0:
        report["error"] = (
            f"The lesson is still {report['total_minutes']} minutes after {rounds} automatic revision "
            f"round(s); it does not meet the {limit}-minute limit. Shorten sections manually."
        )
    return content, report
