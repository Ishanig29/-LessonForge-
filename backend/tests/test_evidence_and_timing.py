"""Claim-to-evidence mapping, missing-citation detection and the 45-minute rule."""
import copy

from app.services.generation.evidence import excerpt_found, extract_passages, verify_claims
from app.services.qc.factual import automated_checks
from app.services.timing.planner import analyze_timing, enforce_time_limit
from tests.conftest import HTTP_TEXT, FakeLLM, make_lesson


class Src:
    def __init__(self, use, content):
        self.evidence_use, self.content = use, content


SOURCES = {"S1": Src("evidence", HTTP_TEXT), "S2": Src("further_reading", None)}


def test_excerpt_matching_is_exact_or_near_exact():
    assert excerpt_found("The 4xx (Client Error) class of status code indicates", HTTP_TEXT)
    assert excerpt_found("the GET,   HEAD, OPTIONS, and TRACE methods are defined to be SAFE", HTTP_TEXT)
    assert not excerpt_found("GET requests can delete resources on the origin server", HTTP_TEXT)
    assert not excerpt_found("", HTTP_TEXT)


def test_verify_claims_assigns_conservative_statuses():
    claims = make_lesson()["claims"]
    out = {c["id"]: c for c in verify_claims(claims, SOURCES)}
    assert out["C1"]["status"] == "Supported"
    assert out["C2"]["status"] == "Unable to Verify" and "NOT found" in out["C2"]["verification_note"]
    assert out["C3"]["status"] == "Unsupported" and out["C3"]["needs_research"]
    # Unknown ID S99 is dropped, and a book alone cannot verify anything.
    assert out["C4"]["source_ids"] == ["S2"]
    assert out["C4"]["status"] == "Unable to Verify" and "metadata-only" in out["C4"]["verification_note"]


def test_missing_citation_detection():
    doc = make_lesson()
    doc["claims"] = verify_claims(doc["claims"], SOURCES)
    issues = automated_checks(doc)
    by_claim = {i["claim_id"]: i for i in issues if i["claim_id"]}
    assert by_claim["C3"]["severity"] == "High" and "no supporting citation" in by_claim["C3"]["explanation"]
    assert "does not appear" in by_claim["C2"]["explanation"]
    assert by_claim["C4"]["severity"] == "Medium"


def test_passage_extraction_prefers_relevant_text():
    text = "Cats are nice animals that sleep a lot.\n\n" + HTTP_TEXT
    passages = extract_passages(text, {"idempotent", "put", "delete"})
    assert any("idempotent" in p for p in passages)
    assert not any(p.startswith("Cats") for p in passages)


def test_timing_sum_and_compliance():
    report = analyze_timing(make_lesson(40))
    assert report["total_minutes"] == 40 and report["compliant"]
    assert sum(s["duration_minutes"] for s in report["sections"]) == report["total_minutes"]
    over = analyze_timing(make_lesson(52))
    assert not over["compliant"] and over["over_by"] == 7
    zero = make_lesson(40)
    zero["sections"][5]["duration_minutes"] = 0  # activity with no time
    assert not analyze_timing(zero)["compliant"]


def test_enforce_time_limit_revises_then_validates():
    llm = FakeLLM()
    llm.queue("timing_revision", {"sections": [{"id": "s1", "duration_minutes": 6}, {"id": "ghost", "duration_minutes": 1}]})
    doc, report = enforce_time_limit(copy.deepcopy(make_lesson(46)), llm)
    assert report["compliant"] and report["total_minutes"] == 40
    assert report["revision_rounds"][0]["before"] == 46


def test_enforce_time_limit_reports_failure_honestly():
    llm = FakeLLM()
    llm.queue("timing_revision", {"sections": [{"id": "s1", "duration_minutes": 14}]})  # model does not shorten
    doc, report = enforce_time_limit(copy.deepcopy(make_lesson(60)), llm)
    assert not report["compliant"] and len(report["revision_rounds"]) == 2
    assert "does not meet" in report["error"]


def test_generate_over_limit_saves_work_but_fails_step(client, fake_llm, providers):
    fake_llm.responses["lesson_generation"] = [make_lesson(60)]
    fake_llm.queue("timing_revision", {"sections": []})
    lid = client.post("/api/lessons", json={"title": "HTTP Requests and Responses",
                                            "learning_objective": "Explain GET and POST methods clearly."}).json["id"]
    client.post(f"/api/lessons/{lid}/analyze-objective")
    client.post(f"/api/lessons/{lid}/research")
    r = client.post(f"/api/lessons/{lid}/generate")
    assert r.status_code == 422 and r.json["error"]["code"] == "timing_limit_exceeded"
    lesson = client.get(f"/api/lessons/{lid}").json
    step = next(s for s in lesson["workflow"] if s["name"] == "timing_validation")
    assert step["status"] == "Failed"
    assert lesson["current_version"] is not None  # generated work preserved
    assert lesson["timing"]["compliant"] is False
    # Cannot be finalized while non-compliant.
    assert client.post(f"/api/lessons/{lid}/finalize", json={"acknowledge_warnings": True}).status_code == 422


def test_generated_lesson_keeps_original_objective_and_builds_references(client, generated):
    lesson = client.get(f"/api/lessons/{generated}").json
    content = lesson["current_version"]["content"]
    assert content["learning_objective"].startswith("Explain GET and POST methods")
    assert content["title"] == "HTTP Requests and Responses"
    assert content["reference_ids"] == ["S1", "S2"]  # cited web source + book as further reading
    assert content["supplementary_video_ids"] == ["S3"]
    analysis = lesson["objective_analysis"]
    assert analysis["original_objective"] == content["learning_objective"]
    claims = client.get(f"/api/lessons/{generated}/claims").json["claims"]
    assert {c["id"]: c["status"] for c in claims}["C3"] == "Unsupported"
