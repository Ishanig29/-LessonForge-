# Implementation status

_Last updated: 2026-11-07_

## Credentials you need to provide (backend/.env)

| Variable | Needed for | Status in build environment |
|---|---|---|
| `GEMINI_API_KEY` | objective analysis, generation, timing revision, both QC layers, AI section revision | **Not available — live calls unverified** |
| `TAVILY_API_KEY` | web research (the only evidence source) | **Not available — live calls unverified** |
| `YOUTUBE_API_KEY` | supplementary videos | **Not available — live calls unverified** |
| `GOOGLE_BOOKS_API_KEY` | optional (higher quota) | Endpoint unreachable from sandbox network — **unverified** |
| `GEMINI_MODEL` | default `gemini-3.5-flash` (listed on Google's deprecation page as released May 2026 with no shutdown date when checked) | Change it if the call returns "model not found" |

Without keys the app runs, shows which integration is missing (Settings page and step errors), and nothing is faked. `DEMO_MODE=true` gives a fully labelled offline walkthrough.

## Acceptance checklist

| Item | Status | Evidence |
|---|---|---|
| React application starts locally | ✅ Verified | Vite dev server ran; Playwright walkthrough |
| Flask backend starts locally | ✅ Verified | `python run.py`, `/api/health` ok |
| Database created automatically | ✅ Verified | `backend/instance/lessonforge.db` created on start |
| Title + objective can be submitted | ✅ Verified | UI + tests |
| Objective analysis works | ✅ Code + mocked tests + demo · ⚠️ live Gemini unverified | |
| Website research works with valid credentials | ⚠️ Implemented, parsing tested with mocked responses; **live unverified** | |
| Book search works or reports missing credentials | ✅ Failure reporting verified (network error surfaced) · ⚠️ live results unverified | |
| YouTube search works with valid credentials | ⚠️ Implemented, parsing + duration tested; **live unverified** | |
| Research sources stored persistently | ✅ Verified | tests, library page |
| Claims have source mappings or explicit unsupported status | ✅ Verified | verifier tests, demo lessons include one Unsupported claim each |
| Structured lesson generation | ✅ Schema/validation/post-processing verified · ⚠️ live Gemini quality unverified | |
| Duration programmatically validated ≤ 45 | ✅ Verified | pass / revise / honest-failure tests; HTTP demo revised 50 → 45 |
| QC Layer 1 runs independently | ✅ Verified (mocked + demo) | |
| QC Layer 2 runs independently | ✅ Verified (mocked + demo) | isolation test; prompt-independence test |
| Separate structured reports displayed and stored | ✅ Verified | |
| Recommendations reviewed and applied | ✅ Verified | apply / reject / review / undo / conflict tests; applied in browser |
| Instructor edits saved | ✅ Verified | autosave in browser ("Saved"), survives reload |
| Previous versions preserved | ✅ Verified | |
| Editing marks QC reports stale | ✅ Verified | UI + export manifest |
| Saved work survives failures and restarts | ✅ Verified | failed-stage test; backend restarted mid-session, data intact |
| Failed steps can be retried | ✅ Verified | per-step and per-provider retry |
| Final preview works | ✅ Verified | |
| Lesson + references export | ✅ Verified | PDF, MD, JSON, CSV |
| Both QC reports export | ✅ Verified | PDF, MD, JSON |
| Complete ZIP export | ✅ Verified | downloaded via browser; manifest checked |
| Both required topics tested | ✅ In demo mode (fixture research + rule-based stand-in) · ⚠️ **not with live AI/research** | see TEST_REPORT.md |
| Automated tests run | ✅ 47 backend + 12 frontend passing | |
| README and documentation | ✅ | README, docs/* |
| Demo script | ✅ | docs/DEMO_SCRIPT.md |

## What you should do first with real keys
1. Fill `backend/.env`, restart, and open **Settings** to confirm all integrations show *Configured*.
2. Run both demonstration topics from **Create Lesson**.
3. If Gemini returns a 404 model error, set `GEMINI_MODEL` to a current model ID.
4. Update TEST_REPORT.md's "live run" section with what you observe.

## Known limitations
See README → Known limitations. Main ones: live APIs unverified here; quote matching proves provenance, not meaning; synchronous stage requests; no transcripts or book text by design.
