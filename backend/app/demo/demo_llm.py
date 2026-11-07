"""Offline demo stand-in for the LLM.

This is NOT an AI model and never claims to be one: every output it produces is
labelled "[Demo stand-in]" and every report records the model as
``demo-stand-in (offline, rule-based)``.

* Objective analysis and lesson generation return the fixture content in
  ``lessons.py`` (claims resolved to the real stored source IDs).
* Timing revision deterministically trims the longest sections.
* Both QC "evaluators" are small rule-based checkers that compute every score
  from the actual lesson they receive (claim statuses, outcome coverage,
  section structure, timing, key-fact regexes) so scores respond to edits.
  Criteria a rule cannot judge are scored 0 and say so.
"""
from __future__ import annotations

import copy
import json
import re

from ..utils.errors import AppError
from .demo_research import detect_topic
from .lessons import ANALYSIS, KEY_FACTS, LESSONS, SOURCE_PLACEHOLDERS

LABEL = "[Demo stand-in — rule-based, not an AI model]"
HIGH_TIERS = ("Official standard", "Official documentation", "Government / university", "Peer-reviewed / scholarly")


def _between(text: str, start: str, end: str | None) -> str:
    i = text.find(start)
    if i == -1:
        return ""
    i += len(start)
    j = text.find(end, i) if end else -1
    return text[i:j if j != -1 else None].strip()


def _json_block(text: str, start: str, end: str | None):
    block = _between(text, start, end)
    try:
        return json.loads(block)
    except (ValueError, TypeError):
        m = re.search(r"(\{.*\}|\[.*\])", block, re.S)
        return json.loads(m.group(1)) if m else None


class DemoLLM:
    model_name = "demo-stand-in (offline, rule-based)"
    is_demo = True

    def generate_json(self, *, task, system, prompt, schema, temperature=0.3):
        handler = getattr(self, f"_{task}", None)
        if handler is None:
            raise AppError(f"Demo mode has no stand-in for task '{task}'.")
        return schema.model_validate(handler(prompt))

    # -------------------------------------------------------------- helpers
    def _topic(self, prompt: str) -> str:
        title = _between(prompt, "Title:", "\n") or _between(prompt, "Lesson title:", "\n") or \
            _between(prompt, "Lesson:", "\n")
        topic = detect_topic(title + " " + _between(prompt, "objective", "\n"))
        if topic is None:
            raise AppError(
                "Offline demo mode only supports the two demonstration topics. Disable DEMO_MODE and configure "
                "GEMINI_API_KEY for other lessons.", code="demo_topic_unavailable")
        return topic

    # -------------------------------------------------------------- tasks
    def _objective_analysis(self, prompt):
        data = copy.deepcopy(ANALYSIS[self._topic(prompt)])
        data["interpretation"] = f"{LABEL} {data['interpretation']}"
        return data

    def _lesson_generation(self, prompt):
        topic = self._topic(prompt)
        doc = copy.deepcopy(LESSONS[topic])
        pack = _between(prompt, "EVIDENCE PACK", "METADATA-ONLY RESOURCES")
        urls = dict((m.group(2), m.group(1)) for m in re.finditer(r"\[(S\d+)\][^\n]*\nURL: (\S+)", pack))
        resolved = {}
        for ph, needle in SOURCE_PLACEHOLDERS.items():
            resolved[ph] = next((key for url, key in urls.items() if needle in url), None)
        for claim in doc["claims"]:
            claim["source_ids"] = [resolved[s] for s in claim["source_ids"] if resolved.get(s)]
            if not claim["source_ids"]:
                claim["evidence_excerpt"] = None
        doc["learning_objective"] = _between(prompt, "(keep verbatim in the `learning_objective` field):", "\n")
        return doc

    def _timing_revision(self, prompt):
        rows = re.findall(r"- ([a-z0-9_-]+) \((\w+)\): (\d+) min", prompt)
        over = int(re.search(r"over by (\d+)", prompt).group(1))
        sections = [{"id": i, "kind": k, "duration_minutes": int(m)} for i, k, m in rows]
        changed: dict[str, int] = {}
        while over > 0:
            candidates = [s for s in sections if s["duration_minutes"] > 2]
            if not candidates:
                break
            longest = max(candidates, key=lambda s: s["duration_minutes"])
            longest["duration_minutes"] -= 1
            changed[longest["id"]] = longest["duration_minutes"]
            over -= 1
        return {"sections": [{"id": i, "duration_minutes": m} for i, m in changed.items()]}

    def _section_revision(self, prompt):
        content = _between(prompt, "---\n", "\n---")
        suggestion = _between(prompt, "Suggested improvement:", "\n")
        note = f"\n\n> **Reviewer note applied (demo stand-in):** {suggestion}"
        return {"content": content + note,
                "change_summary": f"{LABEL} appended the reviewer's suggestion as a note; a live model would rewrite the text."}

    def _qc_factual(self, prompt):
        topic = self._topic(prompt)
        claims = _json_block(prompt, "CLAIMS WITH AUTOMATED EVIDENCE CHECKS (status set by a deterministic quote matcher)",
                             "SOURCES (metadata") or []
        sources = _json_block(prompt, "SOURCES (metadata and retrieved text excerpts)", "Produce:") or []
        lesson = _json_block(prompt, "LESSON (JSON: sections with content containing claim markers like [C2], and knowledge check)",
                             "CLAIMS WITH AUTOMATED") or {}
        text = " ".join(s.get("content", "") for s in lesson.get("sections", [])).lower()
        n = max(1, len(claims))
        supported = sum(1 for c in claims if c.get("automated_status") == "Supported")
        partial = sum(1 for c in claims if c.get("automated_status") == "Partially Supported")
        cited = {k for c in claims for k in c.get("source_ids", [])}
        cited_src = [s for s in sources if s.get("id") in cited]
        high = sum(1 for s in cited_src if s.get("tier") in HIGH_TIERS)
        facts = KEY_FACTS[topic]
        missing = [label for label, rx in facts if not re.search(rx, text)]
        evidence_sources = sum(1 for s in sources if s.get("evidence_use") == "evidence")
        support_ratio = (supported + 0.5 * partial) / n
        rubric = [
            {"criterion": "factual_correctness", "score": 35 * (len(facts) - len(missing)) / len(facts),
             "rationale": f"{LABEL} {len(facts) - len(missing)} of {len(facts)} required key facts were found in the lesson text. "
                          "A rule-based check cannot detect subtle errors."},
            {"criterion": "evidence_support", "score": 25 * support_ratio,
             "rationale": f"{LABEL} {supported} of {n} claims have a verified quote; {partial} partially supported."},
            {"criterion": "source_reliability", "score": 15 * (high / len(cited_src) if cited_src else 0),
             "rationale": f"{LABEL} {high} of {len(cited_src)} cited sources are standards or official documentation."},
            {"criterion": "consistency", "score": 0,
             "rationale": f"{LABEL} Not assessable by the rule-based stand-in; scored 0. Run with a live model."},
            {"criterion": "research_completeness", "score": 15 * min(1.0, evidence_sources / 4) * (1 - len(missing) / len(facts)),
             "rationale": f"{LABEL} {evidence_sources} evidence sources; {len(missing)} key facts missing."},
        ]
        reviews = [{"claim_id": c["id"], "status": c.get("automated_status") or "Unable to Verify",
                    "rationale": f"{LABEL} mirrors the automated quote check: {c.get('automated_note') or ''}"}
                   for c in claims]
        issues = [{"id": f"F{i}", "severity": "High", "category": "missing_fact", "section_id": None, "claim_id": None,
                   "explanation": f"The lesson does not clearly state: {label}.",
                   "evidence_or_reason": f"{LABEL} key-fact pattern not found in lesson text.",
                   "suggested_improvement": f"Add an explicit, cited sentence stating that {label[0].lower() + label[1:]}."}
                  for i, label in enumerate(missing, 1)]
        findings = [{"source_id": s["id"], "authority": "high" if s.get("tier") in HIGH_TIERS else "medium",
                     "is_primary": s.get("tier") == "Official standard", "relevant": True,
                     "note": f"{LABEL} tier: {s.get('tier')}."} for s in cited_src]
        return {
            "overall_assessment": f"{LABEL} {supported}/{n} claims carry a verified quote from retrieved text; "
                                  f"{len(missing)} required key fact(s) missing. This offline score is computed by rules "
                                  "and is not an AI judgement of accuracy.",
            "rubric": rubric, "claim_reviews": reviews, "source_findings": findings, "issues": issues,
            "missing_important_facts": missing,
            "suggested_additional_research": [f"Find an authoritative source for claim {c['id']}"
                                              for c in claims if not c.get("source_ids")],
        }

    def _qc_instructional(self, prompt):
        lesson = _json_block(prompt, "LESSON (JSON)", "RUBRIC") or {}
        analysis = _json_block(prompt, "OBJECTIVE DECOMPOSITION (JSON)", "SECTION TIMINGS") or {}
        total = int(re.search(r"total (\d+) of (\d+) minutes", prompt).group(1))
        sections = lesson.get("sections", [])
        questions = lesson.get("knowledge_check", [])
        outcomes = analysis.get("learning_outcomes", [])
        covered = {o for q in questions for o in q.get("outcome_ids", [])}
        coverage = [{"outcome": o["outcome"], "covered": o["id"] in covered,
                     "where": [q["id"] for q in questions if o["id"] in q.get("outcome_ids", [])],
                     "note": LABEL} for o in outcomes]
        cov_ratio = (sum(c["covered"] for c in coverage) / len(coverage)) if coverage else 0
        concept = [s for s in sections if s["kind"] == "concept"]
        examples = [s for s in sections if s["kind"] == "worked_example"]
        activity = next((s for s in sections if s["kind"] == "activity"), {"content": ""})
        explained = sum(1 for q in questions if len(q.get("explanation", "")) >= 40)
        code_blocks = sum(s["content"].count("```") // 2 for s in examples)
        with_activity = sum(1 for s in sections if s.get("activity"))
        rubric = [
            {"criterion": "objective_alignment", "score": 20 * cov_ratio,
             "rationale": f"{LABEL} {sum(c['covered'] for c in coverage)}/{len(coverage)} outcomes are measured by a question."},
            {"criterion": "clarity_accessibility", "score": 0,
             "rationale": f"{LABEL} Clarity cannot be judged by rules; scored 0. "
                          f"({sum(len(s['content']) > 400 for s in concept)}/{len(concept)} concept sections exceed 400 characters.)"},
            {"criterion": "structure_progression", "score": 10 if [s['kind'] for s in sections][:1] == ["introduction"]
                and sections[-1]["kind"] == "summary" else 5,
             "rationale": f"{LABEL} checks the lesson opens with an introduction and closes with a summary."},
            {"criterion": "examples_applications", "score": min(15, 5 * code_blocks + (5 if any(s['kind'] == 'application' for s in sections) else 0)),
             "rationale": f"{LABEL} {code_blocks} worked code/message examples; application section present."},
            {"criterion": "engagement_activities", "score": 10 if re.search(r"^\s*1\.", activity["content"], re.M) and "Expected" in activity["content"] else 4,
             "rationale": f"{LABEL} activity has numbered tasks and an expected-answer key."},
            {"criterion": "assessment_quality", "score": 15 * explained / max(1, len(questions)),
             "rationale": f"{LABEL} {explained}/{len(questions)} questions include an explanation of 40+ characters."},
            {"criterion": "timing_realism", "score": 10 if total <= 45 else 0,
             "rationale": f"{LABEL} total {total} minutes against the 45-minute limit."},
            {"criterion": "teaching_readiness", "score": 5 * with_activity / max(1, len(sections)),
             "rationale": f"{LABEL} {with_activity}/{len(sections)} sections state what the learner/instructor does."},
        ]
        area = lambda s: {"summary": f"{LABEL} {s}", "strengths": [], "concerns": []}
        issues = []
        apps = next((s for s in sections if s["kind"] == "application"), None)
        if apps and len(apps["content"]) < 600:
            issues.append({"id": "I1", "severity": "Low", "category": "examples", "section_id": apps["id"],
                           "claim_id": None,
                           "explanation": "The real-world applications section is brief and lists uses without a worked scenario.",
                           "evidence_or_reason": f"{LABEL} section length {len(apps['content'])} characters.",
                           "suggested_improvement": "Add one short end-to-end scenario showing the concept used in a real system.",
                           "suggested_text": None})
        return {
            "overall_assessment": f"{LABEL} Structural checks only: outcome coverage {cov_ratio:.0%}, "
                                  f"{len(examples)} worked-example section(s), total {total} minutes. "
                                  "Clarity and pedagogy are not judged offline.",
            "rubric": rubric,
            "findings": {
                "objective_alignment": area(f"{sum(c['covered'] for c in coverage)} of {len(coverage)} outcomes assessed."),
                "clarity": area("Not judged by the rule-based stand-in."),
                "structure": area("Introduction-first and summary-last ordering checked."),
                "examples_and_activities": area(f"{code_blocks} code/message examples found."),
                "assessment": area(f"{len(questions)} questions; {explained} with explanations."),
                "timing": area(f"{total} minutes in total."),
                "teaching_readiness": area(f"{with_activity} of {len(sections)} sections list an activity."),
            },
            "outcome_coverage": coverage,
            "issues": issues,
        }
