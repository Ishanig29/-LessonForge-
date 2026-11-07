# Interview preparation: explaining LessonForge in plain language

## The one-minute pitch
LessonForge takes a lesson title and an objective, works out what learners must be able to do, searches the web, books and YouTube, and writes a lesson of 45 minutes or less in which every important fact points to a passage of real source text. It then runs two separate AI reviewers, one for facts and one for teaching quality, and lets the instructor accept or reject each suggestion. Every change is versioned, and old reviews are marked stale when the lesson changes.

## Why each technology

| Tech | Why |
|---|---|
| **React + TypeScript** | Component model for a multi-tab workspace; TypeScript catches API-shape mistakes (types in `types/api.ts` mirror the backend). |
| **Vite** | Fast dev server, and its proxy keeps the frontend free of backend URLs and keys. |
| **Tailwind** | A consistent design system via tokens (`@theme`) without writing a CSS framework. |
| **Flask** | Small and explicit; easy to read route by route, which matters for a project I need to explain. |
| **SQLAlchemy + SQLite** | Real relational model with constraints and cascades, zero setup locally; switching to Postgres is a `DATABASE_URL` change. |
| **Pydantic** | One place defines both validation of user input and validation of AI output. |
| **Gemini (`google-genai`)** | Required by the brief; JSON response mode suits structured output. Wrapped behind `LLMClient`, so the provider is swappable. |
| **Tavily** | Returns extracted page text, not just links. Evidence needs text. |
| **ReportLab** | Pure-Python PDFs; no headless browser dependency. |
| **Pytest / Vitest** | Standard runners; external APIs are faked so tests run offline. |

## How each API integration works
- **Tavily**: `POST https://api.tavily.com/search` with a Bearer key, `search_depth=advanced`, `chunks_per_source=3`, `include_raw_content=true`. We keep title, URL, domain, snippet, up to 9,000 characters of page text, the published date (if given) and the relevance score.
- **Google Books**: `GET /books/v1/volumes?q=…` (key optional). We keep title, authors, publisher, date, ISBNs, description and links. We never store book text, because we don't have it.
- **YouTube Data API**: `search.list` (type=video, safeSearch strict), then `videos.list` for ISO-8601 durations (`PT12M30S` → 750 s). Metadata only, no transcripts.
- **Gemini**: `client.models.generate_content(model, contents, config=GenerateContentConfig(system_instruction, temperature, response_mime_type="application/json"))`.

## How research is conducted
1. Queries = AI-suggested queries from the objective analysis + the title (+ concept combinations for books, "explained/tutorial" for videos).
2. Each provider runs independently. Errors are recorded per provider, and a missing key stops after the first query.
3. Results are normalised and de-duplicated (canonical URL / ISBN / video ID).
4. Each source is scored: `0.55·authority + 0.30·relevance + 0.15·content availability`, with a stored rationale.
5. Evidence use is decided by rules: web pages with ≥ 200 characters of text and enough relevance are *evidence*; books are *further reading*; videos are *supplementary*; off-topic pages are *excluded*.

## How claims are linked to sources
The model writes claims with source IDs and a verbatim excerpt. Then **my code**, not the model, checks: does the ID exist? Is it an evidence source with text? Does the excerpt actually appear in that text? Only then is a claim "Supported". The fact-check layer later reviews meaning, and the stricter of the two statuses wins.

## How the two QC layers differ
Different prompts, rubrics, routes, buttons, DB rows and workflow steps. Layer 1 sees claims and sources and asks "is it true and backed?". Layer 2 sees outcomes, timings and the learner profile and asks "will it teach?". Layer 2 never sees Layer 1's report (a test checks the prompt). Either can fail or be rerun alone.

## How timing validation works
Python sums the section minutes. If the total is over 45, the AI gets only the numbers and the longest sections, returns new durations for changed sections, and Python recomputes. This happens at most twice; if it is still too long, the step fails honestly, the work is saved and finalization is blocked.

## How data is preserved
- Each stage commits its own result. A failure rolls back only that stage's uncommitted changes.
- Versions are immutable snapshots. Autosaves are merged only into a recent instructor-edit version that hasn't been QC'd.
- Regenerating after edits requires confirmation and creates a new version.
- The browser keeps an unsaved draft in localStorage until the server confirms the save.

## How retries work
- **HTTP/AI level:** timeouts, 5xx and 429 errors are retried up to 2 times with exponential backoff. Bad keys are not retried.
- **AI output:** invalid JSON or schema errors trigger up to 2 "repair" turns that include the validator's message.
- **Workflow level:** a failed step shows its error and a *Retry this step* button; the row moves to *Retrying* and `retry_count` increments. Research can retry one provider.

## Known technical limitations (be upfront)
- Live APIs were not run with real keys in my build environment; they're implemented to the documented APIs and covered by mocked tests.
- Quote matching proves provenance, not entailment.
- Synchronous requests (no job queue); fine for one local user.
- 9,000-character page cap; no full book or video text.
- AI scores are judgements and can vary between runs.

## Likely interview questions

**Q: How do you stop the model inventing references?**
It can only cite source IDs from an evidence pack built from the database. Unknown IDs are deleted by code, references are assembled by code from stored sources, and every excerpt is string-matched against retrieved text.

**Q: Isn't an AI grading AI circular?**
Partly, so I limited what the AI decides. Deterministic checks (quote presence, missing citations, timing, outcome coverage) run first and can't be overridden. The rubric constrains the score, and claim statuses take the more conservative result. The UI and exports call it an assessment.

**Q: What happens if Gemini returns broken JSON?**
`extract_json` handles fences; Pydantic validates; the model gets the validator error and two chances to fix it; then a clear 502 error is shown, the step is marked Failed and can be retried. Nothing half-valid is saved.

**Q: How do you know a QC report is stale?**
Every report stores the SHA-256 of the exact content it evaluated. Freshness = hash equality, computed on read, so it can't drift.

**Q: Why not let the model decide the 45 minutes?**
Models are bad at arithmetic constraints and will claim compliance. The sum is computed in Python and a non-compliant lesson cannot be finalized.

**Q: How would you scale this?**
Move stages to a job queue (RQ/Celery) with the same `workflow_executions` table, switch to Postgres, add auth and per-user ownership, cache research results by query, and stream progress via SSE.

**Q: What would you improve next?**
Fetching full text for top sources via a dedicated extract call; an NLI model for entailment instead of only quote presence; transcript retrieval through the official captions API where licensing allows; side-by-side version diffs.

**Q: What does demo mode actually do?**
It swaps the LLM and research providers at the same seams the tests use. Web text is real documentation captured from GitHub; books and videos are not faked; the "AI" is rule-based and says so in every output.
