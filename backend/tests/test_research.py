"""Research normalisation, de-duplication, evaluation and provider parsing."""
from app.services.research import evaluation as ev
from app.services.research import providers as pv
from app.utils.errors import MissingCredentials
from tests.conftest import FakeProvider, LESSON_INPUT, book, video, web


def test_normalize_url_strips_tracking_www_and_slash():
    a = ev.normalize_url("http://www.Example.com/docs/?utm_source=x&b=2&a=1#frag")
    b = ev.normalize_url("https://example.com/docs?a=1&b=2")
    assert a == b


def test_dedupe_keeps_richest_variant_and_keys_by_type():
    short = web("https://example.com/a", content="short text")
    rich = web("https://www.example.com/a/", content="long " * 100)
    out = ev.dedupe([short, rich, book(isbn="1"), book(title="Other title", isbn="1"), video("v1"), video("v1")])
    assert len(out) == 3
    page = next(s for s in out if s["source_type"] == "website")
    assert page["content"].startswith("long")


def test_authority_tiers():
    assert ev.authority_for("rfc-editor.org")[0] == "Official standard"
    assert ev.authority_for("developer.mozilla.org")[0] == "Official documentation"
    assert ev.authority_for("cs.stanford.edu")[0] == "Government / university"
    assert ev.authority_for("medium.com")[1] < 0.5
    assert ev.authority_for("random-blog.io")[0] == "General website"


def test_evaluation_never_uses_metadata_as_evidence():
    terms = ev.tokenize("HTTP GET POST status codes")
    assert ev.evaluate(book(), terms)["evidence_use"] == "further_reading"
    assert ev.evaluate(video(), terms)["evidence_use"] == "supplementary"
    page = ev.evaluate(web("https://www.rfc-editor.org/rfc/rfc9110.html"), terms)
    assert page["evidence_use"] == "evidence" and page["reliability_tier"] == "Official standard"
    thin = ev.evaluate(web("https://example.com", content="GET POST"), terms)
    assert thin["evidence_use"] == "supplementary"
    off_topic = ev.evaluate(web("https://example.com/cats", content="Cats purr softly " * 30, score=0.0), terms)
    assert off_topic["evidence_use"] == "excluded"


def test_research_route_persists_dedupes_and_keeps_ids_stable(client, fake_llm, providers):
    lid = client.post("/api/lessons", json=LESSON_INPUT).json["id"]
    r = client.post(f"/api/lessons/{lid}/research")
    assert r.status_code == 200
    res = r.json["research"]
    assert res["added"] == 3 and res["duplicates_removed"] == 4  # same results across several queries
    sources = client.get(f"/api/lessons/{lid}/sources").json["sources"]
    assert [s["source_id"] for s in sources] == ["S1", "S2", "S3"]
    assert {s["source_type"] for s in sources} == {"website", "book", "youtube"}

    # Re-running research adds nothing new and keeps the same IDs.
    providers["youtube"].results.append(video("new-vid"))
    r = client.post(f"/api/lessons/{lid}/research")
    sources = client.get(f"/api/lessons/{lid}/sources").json["sources"]
    assert [s["source_id"] for s in sources] == ["S1", "S2", "S3", "S4"]
    assert r.json["lesson"]["workflow"][1]["retry_count"] == 1


def test_provider_failures_are_reported_not_faked(client, fake_llm, providers):
    providers["youtube"].error = MissingCredentials("YouTube key missing")
    providers["tavily"].error = MissingCredentials("Tavily key missing")
    lid = client.post("/api/lessons", json=LESSON_INPUT).json["id"]
    r = client.post(f"/api/lessons/{lid}/research")
    assert r.status_code == 200
    statuses = {p["provider"]: p["status"] for p in r.json["research"]["providers"]}
    assert statuses == {"tavily": "failed", "google_books": "ok", "youtube": "failed"}
    step = next(s for s in r.json["lesson"]["workflow"] if s["name"] == "research")
    assert step["status"] == "Failed" and "Tavily key missing" in step["error_message"]
    # The book result is still saved.
    assert len(client.get(f"/api/lessons/{lid}/sources").json["sources"]) == 1
    # Missing-credential errors stop after the first query (no pointless repeats).
    assert providers["tavily"].calls == 1


def test_retry_single_provider(client, fake_llm, providers):
    providers["tavily"].error = MissingCredentials("Tavily key missing")
    lid = client.post("/api/lessons", json=LESSON_INPUT).json["id"]
    client.post(f"/api/lessons/{lid}/research")
    providers["tavily"].error = None
    r = client.post(f"/api/lessons/{lid}/research", json={"providers": ["tavily"]})
    step = next(s for s in r.json["lesson"]["workflow"] if s["name"] == "research")
    assert step["status"] == "Completed" and step["retry_count"] == 1
    assert providers["google_books"].calls == 1  # not re-run
    assert client.post(f"/api/lessons/{lid}/research", json={"providers": ["bing"]}).status_code == 422


def test_tavily_parsing(monkeypatch):
    def fake_request(method, url, **kw):
        assert kw["headers"]["Authorization"] == "Bearer key"
        return {"results": [
            {"title": "RFC 9110", "url": "https://www.rfc-editor.org/rfc/rfc9110", "content": "chunk",
             "raw_content": "full text " * 2000, "score": 0.8, "published_date": "2022-06-01"},
            {"title": "", "url": "https://bad"},
        ]}
    monkeypatch.setattr(pv, "request_json", fake_request)
    out = pv.TavilyProvider("key").search("http get")
    assert len(out) == 1
    assert out[0]["author_or_domain"] == "rfc-editor.org"
    assert len(out[0]["content"]) == pv.WEB_CONTENT_LIMIT
    try:
        pv.TavilyProvider(None).search("x")
        raise AssertionError("expected MissingCredentials")
    except MissingCredentials as exc:
        assert exc.details["env_var"] == "TAVILY_API_KEY"


def test_books_metadata_only(monkeypatch):
    monkeypatch.setattr(pv, "request_json", lambda *a, **k: {"items": [{
        "id": "vol1", "volumeInfo": {"title": "HTTP", "subtitle": "The Definitive Guide", "authors": ["A", "B"],
                                     "publisher": "P", "publishedDate": "2002",
                                     "industryIdentifiers": [{"type": "ISBN_13", "identifier": "123"}],
                                     "canonicalVolumeLink": "https://books.google.com/x"},
        "searchInfo": {"textSnippet": "snippet"}}]})
    out = pv.GoogleBooksProvider(None).search("http")
    assert out[0]["content"] is None
    assert out[0]["metadata"]["isbn_13"] == "123"
    assert "not accessed" in out[0]["metadata"]["access_note"]


def test_youtube_parsing_and_duration(monkeypatch):
    calls = []

    def fake_request(method, url, **kw):
        calls.append(url)
        if url.endswith("/search"):
            return {"items": [{"id": {"videoId": "v1"}, "snippet": {"title": "T", "channelTitle": "C",
                                                                       "publishedAt": "2023", "thumbnails": {}}}]}
        return {"items": [{"id": "v1", "contentDetails": {"duration": "PT12M30S"}}]}
    monkeypatch.setattr(pv, "request_json", fake_request)
    out = pv.YouTubeProvider("k").search("http")
    assert out[0]["metadata"]["duration_seconds"] == 750
    assert out[0]["content"] is None
    assert pv.parse_iso_duration("PT1H2M") == 3720
    assert pv.parse_iso_duration("garbage") is None
