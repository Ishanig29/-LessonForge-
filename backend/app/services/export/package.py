"""Export orchestration: single files and the complete ZIP package."""
from __future__ import annotations

import io
import json
import re
import zipfile
from datetime import datetime, timezone

from ...models import Lesson, LessonVersion, QCReport
from ...utils.errors import NotFound, ValidationFailed
from ..qc.common import is_stale, latest_reports
from .markdown import (
    lesson_markdown,
    qc_status_line,
    references_csv,
    references_json,
    report_markdown,
    review_status_label,
)
from .pdf import render_pdf

FORMATS = {
    "lesson_pdf", "lesson_markdown", "references_json", "references_csv",
    "qc_factual_pdf", "qc_factual_json", "qc_factual_markdown",
    "qc_instructional_pdf", "qc_instructional_json", "qc_instructional_markdown", "zip",
}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "lesson"


def export_warnings(lesson: Lesson, version: LessonVersion, reports: dict[str, QCReport | None]) -> list[str]:
    warnings = []
    for key, label in (("factual", "Factual accuracy QC"), ("instructional", "Instructional quality QC")):
        r = reports.get(key)
        if r is None:
            warnings.append(f"{label} has not been run.")
        elif is_stale(r, version):
            warnings.append(f"{label} is stale (it evaluated version {r.version_number}).")
    if lesson.finalized_version_id != version.id or lesson.status != "Finalized":
        warnings.append("This lesson version is not finalized; exports are labelled as drafts.")
    if lesson.is_demo:
        warnings.append("This lesson was produced in offline demo mode from fixture data.")
    return warnings


def _report_files(lesson: Lesson, report: QCReport, version: LessonVersion, stem: str) -> dict[str, bytes]:
    md = report_markdown(lesson, report, version)
    footer = f"{lesson.title} · {report.qc_type} QC of v{report.version_number}" + (" · STALE" if is_stale(report, version) else "")
    payload = {
        "lesson_id": lesson.id, "lesson_title": lesson.title, "evaluated_version": report.version_number,
        "current_version": version.version_number, "stale": is_stale(report, version),
        "content_hash": report.content_hash, "model": report.model, "is_demo": report.is_demo,
        "report": report.report,
    }
    return {
        f"{stem}.md": md.encode(),
        f"{stem}.json": json.dumps(payload, indent=2, ensure_ascii=False).encode(),
        f"{stem}.pdf": render_pdf(md, report.report["title"], footer),
    }


def build_export(lesson: Lesson, version: LessonVersion | None, fmt: str) -> tuple[bytes, str, str]:
    """Return (bytes, filename, mimetype)."""
    if fmt not in FORMATS:
        raise ValidationFailed(f"Unknown export format '{fmt}'.", details={"allowed": sorted(FORMATS)})
    if version is None:
        raise ValidationFailed("There is no generated lesson to export yet.")
    reports = latest_reports(lesson)
    base = f"{slug(lesson.title)}-v{version.version_number}"
    footer = f"{lesson.title} · {review_status_label(lesson, version)}"

    if fmt == "lesson_markdown":
        return lesson_markdown(lesson, version, reports).encode(), f"{base}.md", "text/markdown"
    if fmt == "lesson_pdf":
        return render_pdf(lesson_markdown(lesson, version, reports), lesson.title, footer), f"{base}.pdf", "application/pdf"
    if fmt == "references_json":
        return references_json(lesson, version).encode(), f"{base}-references.json", "application/json"
    if fmt == "references_csv":
        return references_csv(lesson, version).encode(), f"{base}-references.csv", "text/csv"
    if fmt.startswith("qc_"):
        kind = "factual" if fmt.startswith("qc_factual") else "instructional"
        report = reports.get(kind)
        if report is None:
            raise NotFound(f"No {kind} QC report exists for this lesson yet.")
        ext = fmt.rsplit("_", 1)[1]
        ext = {"markdown": "md"}.get(ext, ext)
        stem = f"{base}-qc-{kind}-of-v{report.version_number}"
        files = _report_files(lesson, report, version, stem)
        mime = {"pdf": "application/pdf", "json": "application/json", "md": "text/markdown"}[ext]
        return files[f"{stem}.{ext}"], f"{stem}.{ext}", mime

    # Complete package -----------------------------------------------------
    buf = io.BytesIO()
    lesson_md = lesson_markdown(lesson, version, reports)
    contents: list[tuple[str, str]] = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{base}.pdf", render_pdf(lesson_md, lesson.title, footer))
        contents.append((f"{base}.pdf", "Final lesson (PDF)"))
        zf.writestr(f"{base}.md", lesson_md)
        contents.append((f"{base}.md", "Final lesson (Markdown)"))
        zf.writestr("references.json", references_json(lesson, version))
        zf.writestr("references.csv", references_csv(lesson, version))
        contents += [("references.json", "All research sources with reliability and evidence-use"),
                     ("references.csv", "Same sources as CSV")]
        for kind, label in (("factual", "Factual accuracy audit (QC Layer 1)"),
                            ("instructional", "Instructional quality audit (QC Layer 2)")):
            report = reports.get(kind)
            if report is None:
                continue
            stem = f"qc-{kind}-report-of-v{report.version_number}"
            for name, data in _report_files(lesson, report, version, stem).items():
                zf.writestr(name, data)
                contents.append((name, label + (" — STALE" if is_stale(report, version) else "")))
        manifest = manifest_text(lesson, version, reports, contents)
        zf.writestr("README.md", manifest)
    return buf.getvalue(), f"{base}-package.zip", "application/zip"


def manifest_text(lesson: Lesson, version: LessonVersion, reports, contents) -> str:
    lines = [
        f"# LessonForge export — {lesson.title}", "",
        f"Exported: {datetime.now(timezone.utc).isoformat()}", "",
        f"- Lesson version: {version.version_number} (content hash `{version.content_hash[:16]}`)",
        f"- Review status: {review_status_label(lesson, version)}",
        f"- {qc_status_line('Factual accuracy QC', reports.get('factual'), version)}",
        f"- {qc_status_line('Instructional quality QC', reports.get('instructional'), version)}",
        "", "## Warnings", "",
    ]
    lines += [f"- {w}" for w in export_warnings(lesson, version, reports)] or ["- None."]
    lines += ["", "## Files", ""] + [f"- `{n}` — {d}" for n, d in contents]
    lines += ["", "## Notes", "",
              "- QC scores are AI assessments against an explicit rubric, not guarantees of correctness.",
              "- Book entries are catalogue metadata; video entries are YouTube metadata. Neither was read in full "
              "and neither is used as evidence for specific claims.",
              "- Every QC report states the lesson version it evaluated. A report marked STALE describes an "
              "earlier version of the content.", ""]
    return "\n".join(lines)
