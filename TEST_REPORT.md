# Test report

_Run on 2026-11-07 in the build sandbox (Linux, Python 3.13, Node 22, headless Chrome)._

## 1. Automated tests: actually run

| Suite | Command | Result |
|---|---|---|
| Backend | `cd backend && pytest` | **47 passed** |
| Frontend unit/component | `cd frontend && npm test` | **12 passed** |
| Frontend typecheck | `cd frontend && npm run typecheck` | **0 errors** |

All external services are replaced by fakes at the network boundary (`FakeLLM`, `FakeProvider`, monkeypatched `request_json`). Everything else runs for real: routes, DB, verifier, timing, QC post-processing, recommendations, versions and exports.

## 2. External API limitations encountered

- No `GEMINI_API_KEY`, `TAVILY_API_KEY` or `YOUTUBE_API_KEY` was available.
- The sandbox network blocks outbound requests to googleapis.com (Google Books returned `ProxyError`, which the app correctly surfaced as "Could not reach Google Books: network error").
- Therefore **no live AI generation, live research or live QC was performed.** These integrations are implemented against the documented APIs, and their response parsing is unit-tested with representative payloads, but they are **unverified** until run with real credentials.

## 3. Demonstration topics: what was genuinely executed

Both topics were run through the **complete workflow in offline demo mode** via the API (pytest `test_demo_mode_full_workflow[...]`) and through the **real browser UI** (Playwright script driving Chrome against `python run.py` + `vite`).

Demo mode means:
- research = real documentation text captured from GitHub repositories of RFC 9110 (httpwg), MDN (mdn/content), PostgreSQL docs (postgres/postgres) and Microsoft Learn (MicrosoftDocs/sql-docs), labelled as fixtures;
- books and videos = **not available** (reported as failed, not faked);
- "AI" = rule-based stand-in returning fixture analysis and lesson content and computing QC scores from rules.

| Operation | HTTP Requests and Responses | Introduction to SQL Joins |
|---|---|---|
| Objective analysis | ✅ (fixture) | ✅ (fixture) |
| Research | ✅ 5 web sources, 15 duplicates removed; books/videos failed honestly | ✅ 2 web sources; books/videos failed honestly |
| Evidence extraction | ✅ 30 passages | ✅ |
| Claim verification | 12 Supported, 1 Unsupported (deliberately unsourced) | 7 Supported, 1 Partially Supported, 1 Unsupported |
| 45-minute validation | Fixture was 50 min → **1 revision round → 45 min** ✅ | 44 min, no revision needed ✅ |
| QC Layer 1 | ✅ 88/100 (rule-based stand-in) | ✅ 78/100 (rule-based stand-in) |
| QC Layer 2 | ✅ 85/100 (rule-based stand-in) | ✅ 85/100 (rule-based stand-in) |
| Separate reports displayed | ✅ | ✅ |
| Edit & autosave | — | ✅ title edited, "Saved" shown, persisted after reload |
| Reports marked stale after edit | — | ✅ |
| Recommendation applied | ✅ (pytest) | ✅ in browser (AUTO-F1 → section `outer`, new version) |
| QC rerun after change | ✅ (pytest) | ✅ in browser |
| Finalize | ✅ (pytest) | ✅ in browser (warning dialog path exercised) |
| Preview & export | ✅ ZIP checked (pytest) | ✅ ZIP downloaded via browser; manifest shows v3, FINALIZED, both reports current |

The demo QC scores are **not** AI judgements and not hardcoded: they are computed from claim statuses, key-fact regexes, outcome coverage, structure and timing. Criteria the rules cannot judge (consistency, clarity) are scored 0. They show the plumbing, not lesson quality.

### Factual checks required by the brief (HTTP topic)
The fixture lesson and key-fact rules cover: GET safe and idempotent (RFC 9110 §9.2.1/9.2.2, verbatim excerpts verified), POST submits enclosed content for processing (§9.3.3, verified), POST not inherently idempotent (MDN POST, verified), 2xx successful / 4xx client error / 5xx server error (§15.3/15.5/15.6, verified). **Whether a live Gemini generation states these correctly has not been tested.**

## 4. Manual UI checks performed (headless Chrome, 1400×900 and 390×844)
Dashboard (empty and populated), Create (validation, example buttons), workspace tabs (Overview, Research with claim drill-down, Content editor, Quality Control, Final Preview, Export with version history), My Lessons, Research Library, Settings, mobile layout (no horizontal overflow after fix). One console error was observed: the expected 409 from finalize-with-warnings before confirmation.

## 5. Bugs found and fixed during testing
- RFC fixture extraction matched the table of contents instead of section bodies → fixed (`rfind`).
- Timing failure returned HTTP 400 instead of 422 → fixed (`TimingLimitExceeded`).
- Demo instructional stand-in gave full clarity credit it couldn't justify → now scores 0 with an explanation.
- Provider error text was squeezed into a narrow column; mobile grids overflowed → layout fixed.
- PDF tables used equal column widths → content-aware widths.

## 6. Live run (to be completed with real keys)
_Fill in after running both topics with `GEMINI_API_KEY`, `TAVILY_API_KEY`, `YOUTUBE_API_KEY`: sources found, claim status counts, timing rounds, QC scores, any errors._
