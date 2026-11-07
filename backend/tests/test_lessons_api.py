"""Input validation, lesson CRUD and persistence."""
from tests.conftest import LESSON_INPUT


def test_create_lesson_persists_and_lists(client):
    r = client.post("/api/lessons", json={**LESSON_INPUT, "difficulty": "Intermediate",
                                          "delivery_mode": "Instructor-led", "audience": "  Bootcamp  "})
    assert r.status_code == 201
    body = r.json
    assert body["status"] == "Draft"
    assert body["audience"] == "Bootcamp"  # whitespace normalised
    assert [w["status"] for w in body["workflow"]] == ["Pending"] * 11

    listed = client.get("/api/lessons").json["lessons"]
    assert len(listed) == 1 and listed[0]["title"] == LESSON_INPUT["title"]
    assert client.get(f"/api/lessons/{body['id']}").json["learning_objective"] == LESSON_INPUT["learning_objective"]


def test_validation_errors_are_descriptive(client):
    r = client.post("/api/lessons", json={"title": "  ", "learning_objective": ""})
    assert r.status_code == 422
    fields = {d["field"] for d in r.json["error"]["details"]}
    assert {"title", "learning_objective"} <= fields

    r = client.post("/api/lessons", json={**LESSON_INPUT, "title": "x" * 201})
    assert r.status_code == 422

    r = client.post("/api/lessons", json={**LESSON_INPUT, "difficulty": "Expert"})
    assert r.status_code == 422

    r = client.post("/api/lessons", json={**LESSON_INPUT, "unexpected": 1})
    assert r.status_code == 422

    r = client.post("/api/lessons", data="not json", content_type="application/json")
    assert r.status_code == 422


def test_search_update_duplicate_delete(client):
    a = client.post("/api/lessons", json=LESSON_INPUT).json["id"]
    client.post("/api/lessons", json={"title": "Introduction to SQL Joins",
                                      "learning_objective": "Explain INNER and OUTER joins on two tables."})
    assert len(client.get("/api/lessons?q=SQL").json["lessons"]) == 1

    r = client.put(f"/api/lessons/{a}", json={"title": "HTTP Basics"})
    assert r.status_code == 200 and r.json["title"] == "HTTP Basics"
    assert client.put(f"/api/lessons/{a}", json={"title": ""}).status_code == 422

    dup = client.post(f"/api/lessons/{a}/duplicate")
    assert dup.status_code == 201 and dup.json["title"].endswith("(copy)")

    assert client.delete(f"/api/lessons/{a}").status_code == 200
    assert client.get(f"/api/lessons/{a}").status_code == 404
    assert len(client.get("/api/lessons").json["lessons"]) == 2


def test_stats_are_derived_from_database(client):
    client.post("/api/lessons", json=LESSON_INPUT)
    stats = client.get("/api/stats").json
    assert stats["lessons_total"] == 1 and stats["lessons_by_status"]["Draft"] == 1


def test_health_never_exposes_secrets(app, client):
    app.config["SETTINGS"].tavily_api_key = "tvly-SECRET-VALUE"
    body = client.get("/api/health").get_data(as_text=True)
    assert "SECRET" not in body
    assert '"configured": true' in body.replace("True", "true") or "configured" in body


def test_unknown_lesson_404_and_errors_are_json(client):
    r = client.get("/api/lessons/999")
    assert r.status_code == 404 and r.json["error"]["code"] == "not_found"
