"""QC report creation, independent execution, stale detection, recommendations, versions."""
from app.utils.errors import ExternalServiceError
from tests.conftest import make_lesson


def _content(client, lid):
    return client.get(f"/api/lessons/{lid}").json["current_version"]["content"]


def test_factual_report_scoring_and_conservative_claims(client, generated):
    r = client.post(f"/api/lessons/{generated}/qc/factual")
    assert r.status_code == 200
    rep = r.json["report"]
    assert rep["score"] == 30 + 25 + 12 + 9 + 0  # clamped and summed by the backend
    body = rep["report"]
    rubric = {row["criterion"]: row for row in body["rubric"]}
    assert rubric["evidence_support"]["score"] == 25
    assert rubric["research_completeness"]["score"] == 0
    claims = {c["claim_id"]: c for c in body["claims"]}
    # The evaluator said "Supported" but the quote was not found: the conservative status wins.
    assert claims["C2"]["evaluator_status"] == "Supported"
    assert claims["C2"]["final_status"] == "Unable to Verify"
    assert claims["C3"]["final_status"] == "Unsupported"
    assert body["ignored_claim_ids"] == ["C77"]
    assert body["claim_counts"]["supported"] == 1
    assert any(i["origin"] == "automated" for i in body["issues"])
    assert rep["stale"] is False and rep["version_number"] == 1


def test_qc_layers_are_separate_and_failure_isolated(client, generated, fake_llm):
    fake_llm.fail["qc_factual"] = ExternalServiceError("Gemini request failed (500).")
    r1 = client.post(f"/api/lessons/{generated}/qc/factual")
    assert r1.status_code == 502
    r2 = client.post(f"/api/lessons/{generated}/qc/instructional")
    assert r2.status_code == 200
    rep = r2.json["report"]["report"]
    assert rep["qc_type"] == "instructional" and r2.json["report"]["score"] == 40
    # The instructional prompt never contains the factual evaluator's output.
    prompt = next(p for t, p in fake_llm.calls if t == "qc_instructional")
    assert "claim_reviews" not in prompt and "QC Layer 1" not in prompt
    wf = {s["name"]: s for s in r2.json["lesson"]["workflow"]}
    assert wf["qc_factual"]["status"] == "Failed" and wf["qc_instructional"]["status"] == "Completed"
    # Retry the failed layer on its own.
    r3 = client.post(f"/api/lessons/{generated}/qc/factual")
    assert r3.status_code == 200
    wf = {s["name"]: s for s in r3.json["lesson"]["workflow"]}
    assert wf["qc_factual"]["retry_count"] == 1
    assert r3.json["lesson"]["status"] == "QC Reviewed"
    reports = client.get(f"/api/lessons/{generated}/reports").json["reports"]
    assert {r["qc_type"] for r in reports} == {"factual", "instructional"}


def test_editing_marks_reports_stale(client, generated):
    client.post(f"/api/lessons/{generated}/qc/factual")
    client.post(f"/api/lessons/{generated}/qc/instructional")
    content = _content(client, generated)
    content["sections"][0]["content"] += "\n\nInstructor addition."
    r = client.put(f"/api/lessons/{generated}/content", json={"content": content, "autosave": True})
    assert r.status_code == 200 and r.json["action"] == "created"
    latest = r.json["lesson"]["latest_reports"]
    assert latest["factual"]["stale"] and latest["instructional"]["stale"]
    assert "Rerun" in latest["factual"]["stale_reason"]
    assert r.json["lesson"]["status"] == "Generated"  # no longer "QC Reviewed"


def test_autosave_coalesces_and_unchanged_is_noop(client, generated):
    content = _content(client, generated)
    content["sections"][0]["title"] = "Edited once"
    r1 = client.put(f"/api/lessons/{generated}/content", json={"content": content, "autosave": True})
    content["sections"][0]["title"] = "Edited twice"
    r2 = client.put(f"/api/lessons/{generated}/content", json={"content": content, "autosave": True})
    r3 = client.put(f"/api/lessons/{generated}/content", json={"content": content, "autosave": True})
    assert (r1.json["action"], r2.json["action"], r3.json["action"]) == ("created", "updated", "unchanged")
    versions = client.get(f"/api/lessons/{generated}/versions").json["versions"]
    assert [v["version_number"] for v in versions] == [2, 1]
    assert versions[1]["origin"] == "generated"  # original preserved
    # Explicit save creates a new version even within the coalescing window.
    content["sections"][0]["title"] = "Edited thrice"
    r4 = client.put(f"/api/lessons/{generated}/content",
                    json={"content": content, "create_version": True, "change_description": "Checkpoint"})
    assert r4.json["version"]["version_number"] == 3


def test_invalid_content_rejected(client, generated):
    content = _content(client, generated)
    content["sections"] = [s for s in content["sections"] if s["kind"] != "activity"]
    r = client.put(f"/api/lessons/{generated}/content", json={"content": content})
    assert r.status_code == 422


def test_apply_recommendation_changes_only_target_section(client, generated):
    client.post(f"/api/lessons/{generated}/qc/factual")
    before = _content(client, generated)
    recs = client.get(f"/api/lessons/{generated}/recommendations").json["recommendations"]
    rec = next(r for r in recs if r["issue_key"] == "F1")
    r = client.post(f"/api/lessons/{generated}/recommendations/{rec['id']}/apply")
    assert r.status_code == 200 and r.json["result"]["method"] == "suggested_text"
    after = r.json["lesson"]["current_version"]["content"]
    for b, a in zip(before["sections"], after["sections"]):
        if b["id"] == "s1":
            assert a["content"] == "Revised section text [C1]."
        else:
            assert a == b
    assert r.json["lesson"]["current_version"]["origin"] == "recommendation"
    assert client.post(f"/api/lessons/{generated}/recommendations/{rec['id']}/apply").status_code == 409

    # Undo restores just that section as a new version.
    u = client.post(f"/api/lessons/{generated}/recommendations/{rec['id']}/undo")
    assert u.status_code == 200
    assert u.json["lesson"]["current_version"]["content"]["sections"][1]["content"] == before["sections"][1]["content"]
    versions = client.get(f"/api/lessons/{generated}/versions").json["versions"]
    assert [v["origin"] for v in versions] == ["undo", "recommendation", "generated"]


def test_ai_scoped_revision_reject_review_and_undo_conflict(client, generated, fake_llm):
    client.post(f"/api/lessons/{generated}/qc/instructional")
    recs = client.get(f"/api/lessons/{generated}/recommendations").json["recommendations"]
    rec = next(r for r in recs if r["issue_key"] == "I1")
    r = client.post(f"/api/lessons/{generated}/recommendations/{rec['id']}/apply")
    assert r.json["result"]["method"] == "ai_section_rewrite"
    prompt = next(p for t, p in fake_llm.calls if t == "section_revision")
    assert "SECTION TO REVISE (id: s4" in prompt
    # Edit the same section, then undo must refuse to overwrite it.
    content = r.json["lesson"]["current_version"]["content"]
    content["sections"][4]["content"] = "Instructor rewrote this."
    client.put(f"/api/lessons/{generated}/content", json={"content": content})
    assert client.post(f"/api/lessons/{generated}/recommendations/{rec['id']}/undo").status_code == 409

    client.post(f"/api/lessons/{generated}/qc/factual")
    recs = client.get(f"/api/lessons/{generated}/recommendations").json["recommendations"]
    other = next(r for r in recs if r["id"] != rec["id"] and r["review_status"] == "pending")
    assert client.post(f"/api/lessons/{generated}/recommendations/{other['id']}/reject").json[
        "recommendation"]["review_status"] == "rejected"
    assert client.post(f"/api/lessons/{generated}/recommendations/{other['id']}/review").json[
        "recommendation"]["review_status"] == "reviewed"


def test_regenerate_requires_confirmation_after_edits(client, generated):
    content = _content(client, generated)
    content["sections"][0]["content"] = "Manual edit"
    client.put(f"/api/lessons/{generated}/content", json={"content": content})
    r = client.post(f"/api/lessons/{generated}/generate")
    assert r.status_code == 409 and r.json["error"]["code"] == "confirm_overwrite_required"
    r = client.post(f"/api/lessons/{generated}/generate", json={"confirm_overwrite": True})
    assert r.status_code == 200
    origins = [v["origin"] for v in client.get(f"/api/lessons/{generated}/versions").json["versions"]]
    assert origins == ["regenerated", "instructor_edit", "generated"]


def test_restore_version(client, generated):
    content = _content(client, generated)
    content["sections"][0]["content"] = "Changed"
    client.put(f"/api/lessons/{generated}/content", json={"content": content})
    v1 = client.get(f"/api/lessons/{generated}/versions").json["versions"][-1]
    r = client.post(f"/api/lessons/{generated}/versions/{v1['id']}/restore")
    assert r.json["lesson"]["current_version"]["content"]["sections"][0]["content"] != "Changed"
    assert r.json["lesson"]["current_version"]["version_number"] == 3


def test_flag_claim_for_research(client, generated):
    r = client.patch(f"/api/lessons/{generated}/claims/C1", json={"needs_research": True})
    assert r.status_code == 200
    claims = {c["id"]: c for c in client.get(f"/api/lessons/{generated}/claims").json["claims"]}
    assert claims["C1"]["needs_research"] is True
    assert client.patch(f"/api/lessons/{generated}/claims/C1", json={}).status_code == 422


def test_failed_stage_retry_preserves_previous_work(client, fake_llm, providers):
    lid = client.post("/api/lessons", json={"title": "HTTP Requests and Responses",
                                            "learning_objective": "Explain GET and POST methods clearly."}).json["id"]
    fake_llm.fail["objective_analysis"] = ExternalServiceError("Gemini request timed out.", code="ai_timeout")
    r = client.post(f"/api/lessons/{lid}/analyze-objective")
    assert r.status_code == 502 and "timed out" in r.json["error"]["message"]
    wf = {s["name"]: s for s in client.get(f"/api/lessons/{lid}").json["workflow"]}
    assert wf["objective_analysis"]["status"] == "Failed"
    assert client.post(f"/api/lessons/{lid}/generate").status_code == 409  # prerequisites enforced
    r = client.post(f"/api/lessons/{lid}/analyze-objective")
    wf = {s["name"]: s for s in r.json["workflow"]}
    assert wf["objective_analysis"]["status"] == "Completed" and wf["objective_analysis"]["retry_count"] == 1
    client.post(f"/api/lessons/{lid}/research")
    client.post(f"/api/lessons/{lid}/generate")
    fake_llm.fail["qc_factual"] = ExternalServiceError("boom")
    client.post(f"/api/lessons/{lid}/qc/factual")
    lesson = client.get(f"/api/lessons/{lid}").json
    assert lesson["current_version"] is not None and lesson["source_count"] == 3


def test_malformed_ai_json_is_repaired_or_rejected():
    from app.services.ai.client import BaseJSONClient, extract_json
    from app.schemas.lesson import ObjectiveAnalysis
    from app.utils.errors import AIOutputInvalid
    from tests.conftest import ANALYSIS
    import json

    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Here you go: {"a": 2} thanks') == {"a": 2}

    class Scripted(BaseJSONClient):
        def __init__(self, replies):
            super().__init__(max_retries=2, backoff_seconds=0)
            self.replies, self.prompts = list(replies), []

        def _call(self, *, system, prompt, temperature):
            self.prompts.append(prompt)
            return self.replies.pop(0)

    client = Scripted(["not json", json.dumps({"interpretation": "x"}), json.dumps(ANALYSIS)])
    out = client.generate_json(task="t", system="s", prompt="p", schema=ObjectiveAnalysis)
    assert out.key_concepts == ANALYSIS["key_concepts"]
    assert "rejected by the validator" in client.prompts[1]

    bad = Scripted(["{}", "{}", "{}"])
    try:
        bad.generate_json(task="t", system="s", prompt="p", schema=ObjectiveAnalysis)
        raise AssertionError("expected AIOutputInvalid")
    except AIOutputInvalid:
        pass


def test_transient_ai_errors_retry_with_backoff():
    from app.services.ai.client import BaseJSONClient
    from app.schemas.qc import SectionRevision

    class Flaky(BaseJSONClient):
        def __init__(self):
            super().__init__(max_retries=2, backoff_seconds=0)
            self.n = 0

        def _call(self, *, system, prompt, temperature):
            self.n += 1
            if self.n < 3:
                raise ExternalServiceError("503", details={"retryable": True})
            return '{"content": "ok", "change_summary": "s"}'

    flaky = Flaky()
    assert flaky.generate_json(task="t", system="s", prompt="p", schema=SectionRevision).content == "ok"
    assert flaky.n == 3


def test_missing_gemini_key_is_reported(client, providers):
    lid = client.post("/api/lessons", json={"title": "HTTP basics", "learning_objective": "Explain GET and POST."}).json["id"]
    r = client.post(f"/api/lessons/{lid}/analyze-objective")
    assert r.status_code == 503 and r.json["error"]["details"]["env_var"] == "GEMINI_API_KEY"


def test_lesson_schema_rejects_missing_sections():
    from app.schemas.lesson import LessonContent
    import pytest

    doc = make_lesson()
    doc["sections"] = doc["sections"][:3]
    with pytest.raises(Exception):
        LessonContent.model_validate(doc)
