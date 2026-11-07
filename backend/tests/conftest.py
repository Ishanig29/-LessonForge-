"""Test fixtures: in-memory DB, a scripted fake LLM and fake research providers.

The fakes replace only the network boundary; every service, verifier, timing
rule, QC post-processor and route runs for real.
"""
from __future__ import annotations

import copy

import pytest

from app import create_app
from app.config.settings import Settings
from app.services.ai import set_llm_override
from app.services.research import set_providers_override

HTTP_TEXT = (
    "Request methods are considered safe if their defined semantics are essentially read-only. "
    "Of the request methods defined by this specification, the GET, HEAD, OPTIONS, and TRACE methods are "
    "defined to be safe.\n\nOf the request methods defined by this specification, PUT, DELETE, and safe request "
    "methods are idempotent.\n\nThe POST method requests that the target resource process the representation "
    "enclosed in the request according to the resource's own specific semantics.\n\nThe 2xx (Successful) class "
    "of status code indicates that the client's request was successfully received, understood, and accepted. "
    "The 4xx (Client Error) class of status code indicates that the client seems to have erred. The 5xx (Server "
    "Error) class of status code indicates that the server is aware that it has erred."
)

ANALYSIS = {
    "interpretation": "Learners explain GET/POST semantics and classify status codes.",
    "learners_should_understand": ["GET is safe"], "learners_should_be_able_to": ["Classify codes"],
    "key_concepts": ["GET", "POST", "status codes", "idempotent"], "expected_difficulty": "Moderate",
    "prerequisites": ["URLs"], "assessment_methods": ["MCQ"],
    "learning_outcomes": [
        {"id": "LO1", "outcome": "Explain GET and POST", "bloom_level": "Understand", "measurable_by": "Q"},
        {"id": "LO2", "outcome": "Classify 2xx, 4xx, 5xx", "bloom_level": "Analyze", "measurable_by": "Q"},
    ],
    "search_queries": ["RFC 9110 GET POST safe idempotent"],
}


def make_lesson(total_minutes: int = 40) -> dict:
    kinds = ["introduction", "concept", "concept", "worked_example", "application", "activity",
             "knowledge_check", "answers", "takeaways", "summary"]
    per = [3, 6, 6, 6, 3, 6, 4, 2, 1, 3]
    scale = total_minutes - sum(per)
    per[1] += scale  # put any difference in the first concept section
    sections = [
        {"id": f"s{i}", "kind": k, "title": f"Section {i} {k}", "duration_minutes": per[i],
         "activity": "Read and discuss", "content": f"Content for {k}. GET is safe [C1]. POST processes data [C2]."}
        for i, k in enumerate(kinds)
    ]
    return {
        "title": "anything", "learning_objective": "anything at all here",
        "learning_outcomes": ["Explain GET and POST", "Classify codes"],
        "target_audience": "Beginners", "assumed_knowledge": "URLs",
        "sections": sections,
        "knowledge_check": [
            {"id": "Q1", "question": "Is GET safe?", "kind": "multiple_choice", "options": ["Yes", "No", "Maybe"],
             "answer": "Yes", "explanation": "GET is defined as safe by RFC 9110.", "outcome_ids": ["LO1"]},
            {"id": "Q2", "question": "What does 4xx mean?", "kind": "short_answer", "options": [],
             "answer": "Client error", "explanation": "4xx indicates the client seems to have erred.",
             "outcome_ids": ["LO2"]},
        ],
        "claims": [
            {"id": "C1", "text": "GET, HEAD, OPTIONS and TRACE are defined to be safe methods.", "section_id": "s1",
             "source_ids": ["S1"],
             "evidence_excerpt": "the GET, HEAD, OPTIONS, and TRACE methods are defined to be safe"},
            {"id": "C2", "text": "POST asks the target resource to process the enclosed representation.",
             "section_id": "s2", "source_ids": ["S1"],
             "evidence_excerpt": "This sentence is not in the source at all and was invented."},
            {"id": "C3", "text": "Browsers warn before resubmitting POST forms.", "section_id": "s2",
             "source_ids": [], "evidence_excerpt": None},
            {"id": "C4", "text": "A book says GET is great.", "section_id": "s1", "source_ids": ["S2", "S99"],
             "evidence_excerpt": "GET is great"},
        ],
    }


def factual_output(**overrides) -> dict:
    out = {
        "overall_assessment": "Mostly accurate.",
        "rubric": [
            {"criterion": "factual_correctness", "score": 30, "rationale": "ok"},
            {"criterion": "evidence_support", "score": 99, "rationale": "over max, must clamp to 25"},
            {"criterion": "source_reliability", "score": 12, "rationale": "ok"},
            {"criterion": "consistency", "score": 9, "rationale": "ok"},
            # research_completeness intentionally missing -> counted as 0
        ],
        "claim_reviews": [
            {"claim_id": "C1", "status": "Supported", "rationale": "S1 states it."},
            {"claim_id": "C2", "status": "Supported", "rationale": "Overly generous."},
            {"claim_id": "C77", "status": "Supported", "rationale": "Unknown claim id"},
        ],
        "source_findings": [{"source_id": "S1", "authority": "high", "is_primary": True, "relevant": True, "note": "RFC"}],
        "issues": [{"id": "F1", "severity": "Medium", "category": "terminology", "section_id": "s1", "claim_id": None,
                    "explanation": "Clarify 'safe'.", "evidence_or_reason": "Learners confuse safe with secure.",
                    "suggested_improvement": "Add a note.", "suggested_text": "Revised section text [C1]."}],
        "missing_important_facts": ["POST is not idempotent"],
        "suggested_additional_research": ["Find source for C3"],
    }
    out.update(overrides)
    return out


def instructional_output() -> dict:
    area = {"summary": "ok", "strengths": ["a"], "concerns": []}
    return {
        "overall_assessment": "Teachable.",
        "rubric": [{"criterion": k, "score": 5, "rationale": "r"} for k in (
            "objective_alignment", "clarity_accessibility", "structure_progression", "examples_applications",
            "engagement_activities", "assessment_quality", "timing_realism", "teaching_readiness")],
        "findings": {k: area for k in ("objective_alignment", "clarity", "structure", "examples_and_activities",
                                       "assessment", "timing", "teaching_readiness")},
        "outcome_coverage": [{"outcome": "Explain GET and POST", "covered": True, "where": ["s1"], "note": ""}],
        "issues": [{"id": "I1", "severity": "Low", "category": "examples", "section_id": "s4", "claim_id": None,
                    "explanation": "Thin applications.", "evidence_or_reason": "Short.",
                    "suggested_improvement": "Add a scenario.", "suggested_text": None}],
    }


class FakeLLM:
    """Returns queued responses per task; records calls for assertions."""

    model_name = "fake-model"
    is_demo = False

    def __init__(self):
        self.responses: dict[str, list] = {}
        self.calls: list[tuple[str, str]] = []
        self.fail: dict[str, Exception] = {}

    def queue(self, task: str, payload):
        self.responses.setdefault(task, []).append(payload)

    def generate_json(self, *, task, system, prompt, schema, temperature=0.3):
        self.calls.append((task, prompt))
        if task in self.fail:
            raise self.fail.pop(task)
        queue = self.responses.get(task)
        if not queue:
            raise AssertionError(f"No fake response queued for task {task}")
        payload = queue.pop(0) if len(queue) > 1 else queue[0]
        payload = payload(prompt) if callable(payload) else copy.deepcopy(payload)
        return schema.model_validate(payload)


class FakeProvider:
    def __init__(self, name, source_type, results=None, error=None):
        self.name, self.source_type = name, source_type
        self.results = results or []
        self.error = error
        self.calls = 0

    def search(self, query, max_results=5):
        self.calls += 1
        if self.error:
            raise self.error
        return [dict(r, query=query) for r in self.results]


def web(url, title="Doc", content=HTTP_TEXT, domain=None, score=0.9):
    from app.services.research.providers import domain_of

    return {"source_type": "website", "provider": "tavily", "title": title, "url": url,
            "author_or_domain": domain or domain_of(url), "description": content[:200], "content": content,
            "published_date": None, "metadata": {}, "provider_score": score}


def book(title="HTTP: The Guide", isbn="9780000000001"):
    return {"source_type": "book", "provider": "google_books", "title": title, "url": "https://books.example/x",
            "author_or_domain": "A. Author", "description": "A book about HTTP GET POST.", "content": None,
            "published_date": "2002", "metadata": {"isbn_13": isbn}, "provider_score": None}


def video(vid="abc123"):
    return {"source_type": "youtube", "provider": "youtube", "title": "HTTP GET vs POST explained",
            "url": f"https://www.youtube.com/watch?v={vid}", "author_or_domain": "Channel",
            "description": "GET and POST status codes", "content": None, "published_date": "2023-01-01",
            "metadata": {"video_id": vid, "duration_seconds": 600}, "provider_score": None}


@pytest.fixture()
def fake_llm():
    llm = FakeLLM()
    llm.queue("objective_analysis", ANALYSIS)
    llm.queue("lesson_generation", make_lesson())
    llm.queue("qc_factual", factual_output())
    llm.queue("qc_instructional", instructional_output())
    llm.queue("section_revision", {"content": "AI revised section text [C1].", "change_summary": "Clarified."})
    set_llm_override(llm)
    yield llm
    set_llm_override(None)


@pytest.fixture()
def providers():
    p = {
        "tavily": FakeProvider("tavily", "website", [
            web("https://www.rfc-editor.org/rfc/rfc9110.html", "RFC 9110"),
            web("https://rfc-editor.org/rfc/rfc9110.html/?utm_source=x", "RFC 9110 duplicate"),
        ]),
        "google_books": FakeProvider("google_books", "book", [book()]),
        "youtube": FakeProvider("youtube", "youtube", [video()]),
    }
    set_providers_override(p)
    yield p
    set_providers_override(None)


@pytest.fixture()
def app():
    settings = Settings()
    settings.database_url = "sqlite:///:memory:"
    settings.demo_mode = False
    settings.gemini_api_key = None
    application = create_app(settings)
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


LESSON_INPUT = {
    "title": "HTTP Requests and Responses",
    "learning_objective": "Explain GET and POST methods and distinguish between 2xx, 4xx, and 5xx response status categories.",
}


@pytest.fixture()
def generated(client, fake_llm, providers):
    """A lesson taken through analysis, research and generation."""
    lid = client.post("/api/lessons", json=LESSON_INPUT).json["id"]
    assert client.post(f"/api/lessons/{lid}/analyze-objective").status_code == 200
    assert client.post(f"/api/lessons/{lid}/research").status_code == 200
    r = client.post(f"/api/lessons/{lid}/generate")
    assert r.status_code == 200, r.json
    return lid
