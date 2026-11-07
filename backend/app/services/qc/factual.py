"""QC Layer 1 — research and factual accuracy.

Pipeline:
1. Deterministic pre-checks (missing citations, metadata-only citations,
   quotes not found in sources, factual sections with no mapped claims).
2. Independent AI audit with its own system prompt and rubric.
3. Backend post-processing: unknown claim IDs dropped, unreviewed claims
   defaulted to "Unable to Verify", the more conservative of the automated and
   AI status kept per claim, score summed from the clamped rubric.
"""
from __future__ import annotations

import json

from ...models import Lesson, LessonVersion
from ...prompts.templates import FACTUAL_PROMPT, FACTUAL_SYSTEM
from ...schemas.qc import FACTUAL_RUBRIC, FactualQCOutput
from .._text import truncate
from .common import score_rubric, severity_counts, sort_issues

FACTUAL_SECTION_KINDS = {"concept", "worked_example", "application"}
# Higher number = weaker support. Used to keep the more conservative status.
STATUS_RANK = {
    "Supported": 0,
    "Partially Supported": 1,
    "Unable to Verify": 2,
    "Conflicting Evidence": 3,
    "Unsupported": 4,
}
STATUS_KEYS = {
    "Supported": "supported",
    "Partially Supported": "partially_supported",
    "Unsupported": "unsupported",
    "Conflicting Evidence": "conflicting_evidence",
    "Unable to Verify": "unable_to_verify",
}


def automated_checks(content: dict) -> list[dict]:
    issues: list[dict] = []
    n = 0

    def add(**kw):
        nonlocal n
        n += 1
        issues.append({"id": f"AUTO-F{n}", "category": "automated_check", "suggested_text": None, **kw})

    for c in content.get("claims", []):
        if not c.get("source_ids"):
            add(severity="High", section_id=c["section_id"], claim_id=c["id"],
                explanation=f"Claim {c['id']} has no supporting citation: “{truncate(c['text'], 160)}”",
                evidence_or_reason="Missing-citation detector: no source ID is attached to this claim.",
                suggested_improvement="Add research that supports this claim, cite it, or remove/soften the claim.")
        elif c.get("status") == "Unable to Verify" and "NOT found" in (c.get("verification_note") or ""):
            add(severity="High", section_id=c["section_id"], claim_id=c["id"],
                explanation=f"The evidence quote for {c['id']} does not appear in the cited source text.",
                evidence_or_reason=c.get("verification_note") or "",
                suggested_improvement="Replace the excerpt with a passage that actually appears in the source, or re-research.")
        elif c.get("status") == "Unable to Verify" and "metadata-only" in (c.get("verification_note") or ""):
            add(severity="Medium", section_id=c["section_id"], claim_id=c["id"],
                explanation=f"Claim {c['id']} relies only on metadata (book/video) that cannot verify it.",
                evidence_or_reason=c.get("verification_note") or "",
                suggested_improvement="Support this claim with retrieved text from an authoritative web source.")
    claimed_sections = {c["section_id"] for c in content.get("claims", [])}
    for s in content.get("sections", []):
        if s["kind"] in FACTUAL_SECTION_KINDS and s["id"] not in claimed_sections and len(s.get("content", "")) > 300:
            add(severity="Low", section_id=s["id"], claim_id=None,
                explanation=f"Section '{s['title']}' contains explanatory content but no mapped factual claims.",
                evidence_or_reason="Traceability check: factual statements here cannot be traced to evidence.",
                suggested_improvement="Identify the key factual statements in this section and map them to sources.")
    return issues


def _sources_payload(lesson: Lesson, cited: set[str]) -> str:
    rows = []
    for s in sorted(lesson.sources, key=lambda s: s.source_key):
        if s.evidence_use == "excluded" and s.source_key not in cited:
            continue
        passages = (s.extra or {}).get("passages") or []
        rows.append({
            "id": s.source_key, "type": s.source_type, "title": s.title, "author_or_domain": s.author_or_domain,
            "url": s.url, "tier": s.reliability_tier, "evidence_use": s.evidence_use,
            "retrieved_text": [truncate(p, 600) for p in passages[:6]] if s.source_key in cited or s.evidence_use == "evidence" else [],
            "note": (s.extra or {}).get("access_note"),
        })
    return truncate(json.dumps(rows, ensure_ascii=False), 50000)


def run_factual_qc(lesson: Lesson, version: LessonVersion, llm) -> tuple[int, dict]:
    content = version.content
    auto_issues = automated_checks(content)
    cited = {k for c in content.get("claims", []) for k in c.get("source_ids", [])}
    claims_payload = [
        {"id": c["id"], "section_id": c["section_id"], "text": c["text"], "source_ids": c["source_ids"],
         "evidence_excerpt": c.get("evidence_excerpt"), "automated_status": c.get("status"),
         "automated_note": c.get("verification_note")}
        for c in content.get("claims", [])
    ]
    lesson_payload = {
        "sections": [{"id": s["id"], "kind": s["kind"], "title": s["title"], "content": s["content"]}
                     for s in content["sections"]],
        "knowledge_check": content["knowledge_check"],
    }
    rubric_text = "\n".join(f"- {k} (max {m}): {d}" for k, (m, d) in FACTUAL_RUBRIC.items())
    out: FactualQCOutput = llm.generate_json(
        task="qc_factual",
        system=FACTUAL_SYSTEM,
        prompt=FACTUAL_PROMPT.format(
            title=lesson.title, objective=lesson.learning_objective, rubric=rubric_text,
            lesson=truncate(json.dumps(lesson_payload, ensure_ascii=False), 60000),
            claims=json.dumps(claims_payload, ensure_ascii=False),
            sources=_sources_payload(lesson, cited),
        ),
        schema=FactualQCOutput,
        temperature=0.1,
    )
    score, rubric_rows = score_rubric(out.rubric, FACTUAL_RUBRIC)

    claims_by_id = {c["id"]: c for c in content.get("claims", [])}
    ai_reviews = {r.claim_id: r for r in out.claim_reviews if r.claim_id in claims_by_id}
    ignored = sorted({r.claim_id for r in out.claim_reviews} - set(claims_by_id))
    claim_rows = []
    for cid, claim in claims_by_id.items():
        auto = claim.get("status") or "Unable to Verify"
        review = ai_reviews.get(cid)
        ai_status = review.status if review else "Unable to Verify"
        final = max((auto, ai_status), key=lambda s: STATUS_RANK[s])
        claim_rows.append({
            "claim_id": cid, "section_id": claim["section_id"], "text": claim["text"],
            "source_ids": claim["source_ids"], "automated_status": auto, "evaluator_status": ai_status,
            "final_status": final,
            "rationale": review.rationale if review else "The evaluator did not review this claim.",
        })
    counts = {v: 0 for v in STATUS_KEYS.values()}
    for row in claim_rows:
        counts[STATUS_KEYS[row["final_status"]]] += 1

    section_ids = {s["id"] for s in content["sections"]}
    issues = [i.model_dump() for i in out.issues]
    for i in issues:
        if i.get("section_id") not in section_ids:
            claim = claims_by_id.get(i.get("claim_id") or "")
            i["section_id"] = claim["section_id"] if claim else None
        i["origin"] = "evaluator"
    for i in auto_issues:
        i["origin"] = "automated"
    all_issues = sort_issues(auto_issues + issues)

    report = {
        "qc_type": "factual",
        "title": "QC Layer 1 — Research & Factual Accuracy Audit",
        "overall_assessment": out.overall_assessment,
        "score": score,
        "score_max": 100,
        "rubric": rubric_rows,
        "score_disclaimer": "An AI-generated score is an assessment, not a guarantee of factual correctness.",
        "claims_reviewed": len(claim_rows),
        "claim_counts": counts,
        "claims": claim_rows,
        "ignored_claim_ids": ignored,
        "source_findings": [f.model_dump() for f in out.source_findings],
        "issues": all_issues,
        "severity_counts": severity_counts(all_issues),
        "missing_important_facts": out.missing_important_facts,
        "suggested_additional_research": out.suggested_additional_research,
        "status_policy": "Final claim status is the more conservative of the automated quote check and the evaluator's review.",
    }
    return score, report
