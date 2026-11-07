"""Markdown/JSON/CSV renderers for lessons, references and QC reports."""
from __future__ import annotations

import csv
import io
import json

from ...models import Lesson, LessonVersion, QCReport
from ...models.entities import iso
from ..qc.common import is_stale
from ..timing.planner import analyze_timing


def review_status_label(lesson: Lesson, version: LessonVersion) -> str:
    if lesson.finalized_version_id == version.id and lesson.status == "Finalized":
        return f"FINALIZED — version {version.version_number}"
    return f"DRAFT — not finalized (version {version.version_number})"


def qc_status_line(name: str, report: QCReport | None, version: LessonVersion) -> str:
    if report is None:
        return f"{name}: NOT RUN"
    if is_stale(report, version):
        return (f"{name}: STALE — score {report.score}/100 was produced for version {report.version_number}; "
                "the lesson has changed since")
    return f"{name}: {report.score}/100 (current, version {report.version_number})"


def _source_line(s) -> str:
    bits = [f"**[{s.source_key}]** {s.title}"]
    if s.author_or_domain:
        bits.append(s.author_or_domain)
    if s.source_type == "book" and (s.extra or {}).get("publisher"):
        bits.append(s.extra["publisher"])
    if s.published_date:
        bits.append(str(s.published_date)[:10])
    line = ". ".join(bits) + "."
    if s.url:
        line += f" <{s.url}>"
    use = {"evidence": "Used as evidence", "further_reading": "Further reading (metadata only)",
           "supplementary": "Supplementary (not used as evidence)", "excluded": "Excluded"}[s.evidence_use]
    line += f" Retrieved {iso(s.retrieved_at)[:10]}. {use}."
    if s.is_demo:
        line += " [OFFLINE DEMO FIXTURE]"
    return line


def lesson_markdown(lesson: Lesson, version: LessonVersion, reports: dict[str, QCReport | None]) -> str:
    c = version.content
    by_key = {s.source_key: s for s in lesson.sources}
    timing = analyze_timing(c)
    out: list[str] = [f"# {c['title']}", ""]
    out.append(f"> **Review status:** {review_status_label(lesson, version)}  ")
    out.append(f"> **Total duration:** {timing['total_minutes']} of {timing['limit_minutes']} minutes "
               f"({'within limit' if timing['compliant'] else 'NOT COMPLIANT'})  ")
    out.append(f"> **{qc_status_line('Factual accuracy QC', reports.get('factual'), version)}**  ")
    out.append(f"> **{qc_status_line('Instructional quality QC', reports.get('instructional'), version)}**")
    if lesson.is_demo:
        out.append("> **OFFLINE DEMO:** generated from labelled fixture data, not live research or live AI.")
    out += ["", "## Learning objective", "", c["learning_objective"], "", "## Expected learning outcomes", ""]
    out += [f"{i}. {o}" for i, o in enumerate(c["learning_outcomes"], 1)]
    out += ["", "## Target audience and assumed knowledge", "", f"**Audience:** {c['target_audience']}", "",
            f"**Assumed knowledge:** {c['assumed_knowledge']}", "", "## Lesson plan", "",
            "| # | Section | Minutes | Activity |", "|---|---|---|---|"]
    for i, s in enumerate(c["sections"], 1):
        out.append(f"| {i} | {s['title']} | {s['duration_minutes']} | {s['activity'].replace('|', '/')} |")
    out.append(f"| | **Total** | **{timing['total_minutes']}** | |")
    for s in c["sections"]:
        out += ["", f"## {s['title']} ({s['duration_minutes']} min)", ""]
        if s.get("activity"):
            out += [f"*Activity:* {s['activity']}", ""]
        out.append(s["content"].strip())
        if s["kind"] == "knowledge_check":
            for q in c["knowledge_check"]:
                out += ["", f"**{q['id']}.** {q['question']}"]
                for j, opt in enumerate(q.get("options") or []):
                    out.append(f"   {chr(65 + j)}. {opt}")
        if s["kind"] == "answers":
            for q in c["knowledge_check"]:
                outcomes = f" _(measures {', '.join(q['outcome_ids'])})_" if q.get("outcome_ids") else ""
                out += ["", f"**{q['id']} answer:** {q['answer']}{outcomes}", "", q["explanation"]]
    videos = [by_key[k] for k in c.get("supplementary_video_ids", []) if k in by_key]
    out += ["", "## Supplementary video resources", ""]
    if videos:
        out.append("_Selected from YouTube search metadata. Transcripts were not reviewed; watch before assigning._")
        out.append("")
        for v in videos:
            dur = (v.extra or {}).get("duration_seconds")
            dur_txt = f" ({dur // 60} min)" if dur else ""
            out.append(f"- [{v.title}]({v.url}) — {v.author_or_domain or 'unknown channel'}{dur_txt}")
    else:
        out.append("_No videos were retrieved for this lesson._")
    out += ["", "## Claim evidence map", "", "| Claim | Section | Sources | Status |", "|---|---|---|---|"]
    for cl in c.get("claims", []):
        text = cl["text"].replace("|", "/")
        out.append(f"| {cl['id']}: {text} | {cl['section_id']} | {', '.join(cl['source_ids']) or '—'} | {cl.get('status')} |")
    refs = [by_key[k] for k in c.get("reference_ids", []) if k in by_key]
    out += ["", "## References", ""]
    out += [f"- {_source_line(s)}" for s in refs] or ["_No references._"]
    out.append("")
    return "\n".join(out)


def references_payload(lesson: Lesson, version: LessonVersion | None) -> list[dict]:
    cited = set()
    if version:
        cited = {k for c in version.content.get("claims", []) for k in c.get("source_ids", [])}
    rows = []
    for s in sorted(lesson.sources, key=lambda s: int(s.source_key[1:])):
        rows.append({
            "source_id": s.source_key, "type": s.source_type, "title": s.title, "url": s.url,
            "author_or_domain": s.author_or_domain, "published_date": s.published_date,
            "retrieved_at": iso(s.retrieved_at), "reliability_tier": s.reliability_tier,
            "reliability_score": s.reliability_score, "reliability_rationale": s.reliability_rationale,
            "evidence_use": s.evidence_use, "cited_by_claims": s.source_key in cited,
            "provider": s.provider, "is_demo_fixture": s.is_demo,
            "isbn": (s.extra or {}).get("isbn_13") or (s.extra or {}).get("isbn_10"),
            "publisher": (s.extra or {}).get("publisher"),
        })
    return rows


def references_json(lesson: Lesson, version: LessonVersion | None) -> str:
    return json.dumps({
        "lesson_id": lesson.id, "lesson_title": lesson.title,
        "lesson_version": version.version_number if version else None,
        "sources": references_payload(lesson, version),
    }, indent=2, ensure_ascii=False)


def references_csv(lesson: Lesson, version: LessonVersion | None) -> str:
    rows = references_payload(lesson, version)
    buf = io.StringIO()
    fields = list(rows[0].keys()) if rows else ["source_id"]
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def report_markdown(lesson: Lesson, report: QCReport, current: LessonVersion | None) -> str:
    r = report.report
    stale = is_stale(report, current)
    out = [f"# {r['title']}", "", f"**Lesson:** {lesson.title}  ",
           f"**Evaluated lesson version:** {report.version_number} (content hash {report.content_hash[:12]})  ",
           f"**Generated:** {iso(report.created_at)}  ", f"**Model:** {report.model}  "]
    if stale:
        out.append(f"**STATUS: STALE** — the lesson is now at version {current.version_number if current else '?'}; "
                   "this report does not describe the current content.  ")
    if report.is_demo:
        out.append("**OFFLINE DEMO:** produced by the labelled demo fixture evaluator, not a live model.  ")
    out += ["", f"## Score: {r['score']} / 100", "", f"_{r['score_disclaimer']}_", "",
            "| Criterion | Score | Max | Rationale |", "|---|---|---|---|"]
    for row in r["rubric"]:
        out.append(f"| {row['criterion']} | {row['score']} | {row['max']} | {row['rationale'].replace('|', '/')} |")
    out += ["", "## Overall assessment", "", r["overall_assessment"], ""]
    if r["qc_type"] == "factual":
        cc = r["claim_counts"]
        out += ["## Claims", "", f"Reviewed: {r['claims_reviewed']} · Supported: {cc['supported']} · "
                f"Partially supported: {cc['partially_supported']} · Unsupported: {cc['unsupported']} · "
                f"Conflicting: {cc['conflicting_evidence']} · Unable to verify: {cc['unable_to_verify']}", "",
                "| Claim | Automated | Evaluator | Final | Rationale |", "|---|---|---|---|---|"]
        for c in r["claims"]:
            out.append(f"| {c['claim_id']}: {c['text'].replace('|', '/')} | {c['automated_status']} | "
                       f"{c['evaluator_status']} | **{c['final_status']}** | {c['rationale'].replace('|', '/')} |")
        out += ["", "## Source quality findings", ""]
        out += [f"- **{f['source_id']}** — authority {f['authority']}, {'primary' if f['is_primary'] else 'secondary'}"
                f"{'' if f['relevant'] else ', not relevant'}: {f['note']}" for f in r["source_findings"]] or ["_None._"]
    else:
        out += ["## Findings", ""]
        for area, f in r["findings"].items():
            out += [f"### {area.replace('_', ' ').title()}", "", f["summary"], ""]
            out += [f"- ✓ {s}" for s in f["strengths"]] + [f"- ⚠ {s}" for s in f["concerns"]] + [""]
        out += ["## Learning outcome coverage", ""]
        out += [f"- {'✓' if o['covered'] else '✗'} {o['outcome']} — {', '.join(o['where']) or 'not found'} {o['note']}"
                for o in r["outcome_coverage"]] or ["_Not reported._"]
        t = r["timing"]
        out += ["", f"**Timing:** {t['total_minutes']}/{t['limit_minutes']} min, "
                f"{'compliant' if t['compliant'] else 'NOT compliant'}."]
    out += ["", "## Issues", ""]
    sc = r["severity_counts"]
    out.append(" · ".join(f"{k}: {v}" for k, v in sc.items()))
    for i in r["issues"]:
        target = ", ".join(filter(None, [i.get("section_id") and f"section {i['section_id']}",
                                          i.get("claim_id") and f"claim {i['claim_id']}"])) or "whole lesson"
        out += ["", f"### {i['id']} · {i['severity']} · {i['category']} ({target})", "",
                i["explanation"], "", f"**Evidence / reason:** {i['evidence_or_reason']}", "",
                f"**Suggested improvement:** {i['suggested_improvement']}"]
        if i.get("suggested_text"):
            out += ["", "**Suggested revised text:**", "", "```markdown", i["suggested_text"], "```"]
    if r["qc_type"] == "factual":
        out += ["", "## Missing important facts", ""] + ([f"- {m}" for m in r["missing_important_facts"]] or ["_None identified._"])
        out += ["", "## Suggested additional research", ""] + ([f"- {m}" for m in r["suggested_additional_research"]] or ["_None._"])
    out.append("")
    return "\n".join(out)
