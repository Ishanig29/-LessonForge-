"""Exports, finalization and the end-to-end offline demo workflow."""
import io
import json
import zipfile

import pytest

from app import create_app
from app.config.settings import Settings


def test_exports_all_formats(client, generated):
    client.post(f"/api/lessons/{generated}/qc/factual")
    for fmt, mime in [("lesson_pdf", "application/pdf"), ("lesson_markdown", "text/markdown"),
                      ("references_json", "application/json"), ("references_csv", "text/csv"),
                      ("qc_factual_pdf", "application/pdf"), ("qc_factual_json", "application/json"),
                      ("qc_factual_markdown", "text/markdown")]:
        r = client.post(f"/api/lessons/{generated}/export", json={"format": fmt})
        assert r.status_code == 200, (fmt, r.get_data(as_text=True)[:200])
        assert r.mimetype == mime
        assert "-v1" in r.headers["Content-Disposition"]
    pdf = client.post(f"/api/lessons/{generated}/export", json={"format": "lesson_pdf"}).data
    assert pdf.startswith(b"%PDF")
    md = client.post(f"/api/lessons/{generated}/export", json={"format": "lesson_markdown"}).get_data(as_text=True)
    assert "DRAFT — not finalized" in md and "Instructional quality QC: NOT RUN" in md
    assert "| **Total** | **40** |" in md
    refs = json.loads(client.post(f"/api/lessons/{generated}/export", json={"format": "references_json"}).data)
    assert [s["source_id"] for s in refs["sources"]] == ["S1", "S2", "S3"]
    assert client.post(f"/api/lessons/{generated}/export",
                       json={"format": "qc_instructional_pdf"}).status_code == 404
    assert client.post(f"/api/lessons/{generated}/export", json={"format": "docx"}).status_code == 422


def test_zip_package_labels_stale_reports(client, generated):
    client.post(f"/api/lessons/{generated}/qc/factual")
    client.post(f"/api/lessons/{generated}/qc/instructional")
    content = client.get(f"/api/lessons/{generated}").json["current_version"]["content"]
    content["sections"][0]["content"] = "Edited after QC"
    client.put(f"/api/lessons/{generated}/content", json={"content": content})
    pre = client.get(f"/api/lessons/{generated}/export/preflight").json
    assert any("stale" in w for w in pre["warnings"])
    r = client.post(f"/api/lessons/{generated}/export", json={"format": "zip"})
    z = zipfile.ZipFile(io.BytesIO(r.data))
    names = set(z.namelist())
    assert {"README.md", "references.json", "references.csv"} <= names
    assert any(n.startswith("qc-factual-report-of-v1") and n.endswith(".pdf") for n in names)
    assert any(n.startswith("qc-instructional-report-of-v1") for n in names)
    readme = z.read("README.md").decode()
    assert "STALE" in readme and "Lesson version: 2" in readme
    report_md = z.read(next(n for n in names if n.startswith("qc-factual") and n.endswith(".md"))).decode()
    assert "STATUS: STALE" in report_md


def test_finalize_requires_acknowledging_warnings(client, generated):
    r = client.post(f"/api/lessons/{generated}/finalize")
    assert r.status_code == 409 and r.json["error"]["code"] == "warnings_require_acknowledgement"
    client.post(f"/api/lessons/{generated}/qc/factual")
    client.post(f"/api/lessons/{generated}/qc/instructional")
    r = client.post(f"/api/lessons/{generated}/finalize")
    assert r.status_code == 200 and r.json["status"] == "Finalized" and r.json["is_current_finalized"]
    md = client.post(f"/api/lessons/{generated}/export", json={"format": "lesson_markdown"}).get_data(as_text=True)
    assert "FINALIZED — version 1" in md
    # Editing a finalized lesson returns it to draft review status.
    content = r.json["current_version"]["content"]
    content["sections"][0]["content"] = "Post-final edit"
    r = client.put(f"/api/lessons/{generated}/content", json={"content": content})
    assert r.json["lesson"]["status"] == "Generated" and not r.json["lesson"]["is_current_finalized"]


def test_research_library_filters(client, generated):
    all_sources = client.get("/api/sources").json["sources"]
    assert len(all_sources) == 3
    assert [s["source_type"] for s in client.get("/api/sources?type=book").json["sources"]] == ["book"]
    assert client.get("/api/sources?q=RFC").json["sources"][0]["lesson_title"] == "HTTP Requests and Responses"


@pytest.fixture()
def demo_client():
    from app.services.ai import set_llm_override
    from app.services.research import set_providers_override

    set_llm_override(None)
    set_providers_override(None)
    s = Settings()
    s.database_url = "sqlite:///:memory:"
    s.demo_mode = True
    return create_app(s).test_client()


TOPICS = [
    ("HTTP Requests and Responses",
     "Explain GET and POST methods and distinguish between 2xx, 4xx, and 5xx response status categories."),
    ("Introduction to SQL Joins",
     "Explain INNER JOIN, LEFT JOIN, RIGHT JOIN and FULL OUTER JOIN, and demonstrate how they combine records "
     "from two relational tables."),
]


@pytest.mark.parametrize("title,objective", TOPICS)
def test_demo_mode_full_workflow(demo_client, title, objective):
    c = demo_client
    lid = c.post("/api/lessons", json={"title": title, "learning_objective": objective}).json["id"]
    assert c.post(f"/api/lessons/{lid}/analyze-objective").status_code == 200
    r = c.post(f"/api/lessons/{lid}/research")
    providers = {p["provider"]: p["status"] for p in r.json["research"]["providers"]}
    assert providers == {"tavily": "ok", "google_books": "failed", "youtube": "failed"}
    sources = c.get(f"/api/lessons/{lid}/sources").json["sources"]
    assert all(s["is_demo"] for s in sources)
    r = c.post(f"/api/lessons/{lid}/generate")
    assert r.status_code == 200, r.json
    assert r.json["timing"]["total_minutes"] <= 45
    lesson = r.json["lesson"]
    assert lesson["is_demo"]
    claims = lesson["current_version"]["content"]["claims"]
    statuses = [c_["status"] for c_ in claims]
    assert statuses.count("Unsupported") == 1  # the deliberately unsourced claim
    assert statuses.count("Supported") >= 6
    f = c.post(f"/api/lessons/{lid}/qc/factual").json["report"]
    i = c.post(f"/api/lessons/{lid}/qc/instructional").json["report"]
    assert f["model"].startswith("demo-stand-in") and f["is_demo"]
    assert 0 < f["score"] < 100 and 0 < i["score"] < 100
    recs = c.get(f"/api/lessons/{lid}/recommendations").json["recommendations"]
    target = next(r_ for r_ in recs if r_["affected_section_id"])
    applied = c.post(f"/api/lessons/{lid}/recommendations/{target['id']}/apply")
    assert applied.status_code == 200
    assert applied.json["lesson"]["latest_reports"]["factual"]["stale"]
    c.post(f"/api/lessons/{lid}/qc/factual")
    c.post(f"/api/lessons/{lid}/qc/instructional")
    assert c.post(f"/api/lessons/{lid}/finalize", json={"acknowledge_warnings": True}).json["status"] == "Finalized"
    z = zipfile.ZipFile(io.BytesIO(c.post(f"/api/lessons/{lid}/export", json={"format": "zip"}).data))
    readme = z.read("README.md").decode()
    assert "offline demo mode" in readme and "FINALIZED" in readme


def test_demo_mode_rejects_other_topics(demo_client):
    lid = demo_client.post("/api/lessons", json={"title": "Photosynthesis basics",
                                                 "learning_objective": "Explain how plants make sugar."}).json["id"]
    r = demo_client.post(f"/api/lessons/{lid}/analyze-objective")
    assert r.status_code == 400 and r.json["error"]["code"] == "demo_topic_unavailable"
