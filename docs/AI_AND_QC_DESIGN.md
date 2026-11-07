# AI and quality-control design

All prompt text lives in `backend/app/prompts/templates.py`. Each AI role has its **own system instruction**.

## 1. Structured output

`LLMClient.generate_json(task, system, prompt, schema)`:

1. Appends the Pydantic schema's JSON Schema to the prompt and requests `response_mime_type="application/json"`.
2. `extract_json` parses the text (tolerating ```` ```json ```` fences or leading prose).
3. `schema.model_validate` enforces types, ID patterns (`LO\d+`, `Q\d+`, `C\d+`), lengths and cross-field rules (required section kinds, unique IDs).
4. On failure, re-asks with the exact validator error (max 2 repairs), then raises `AIOutputInvalid` (HTTP 502, step marked Failed, retryable).
5. Transient errors are retried with exponential backoff, separately from repairs.

**Server-owned fields are never trusted:** claim `status`, `verification_note` and `needs_research` are reset after generation. `reference_ids` and `supplementary_video_ids` are rebuilt from stored sources. The original title and objective are restored. QC scores are recomputed from clamped rubric items.

## 2. Prompts by role

| Role | System instruction (summary) | Output schema |
|---|---|---|
| Objective analyst | Instructional designer. Interpret, don't rewrite; outcomes must use measurable verbs. | `ObjectiveAnalysis` |
| Lesson author | Cite only IDs from the evidence pack; quote excerpts verbatim ≤ 300 chars; empty `source_ids` if unsupported; claim markers in text; no references or video lists; metadata-only items never evidence; durations sum ≤ 45. | `LessonContent` |
| Timing reviser | Shorten realistically, trim content to match, keep required sections and claim markers; return only changed sections. | `TimingRevision` |
| Fact-checker (QC 1) | Independent auditor; conservative; "Unable to Verify" when evidence is insufficient; URL ≠ evidence; books/videos are metadata only; distinguish primary vs secondary. | `FactualQCOutput` |
| Instructional reviewer (QC 2) | Experienced instructional designer; not a fact-checker; specific, quotes the lesson, offers revised text. | `InstructionalQCOutput` |
| Section reviser | Change exactly one section to address one recommendation; no new unsupported claims; never invent sources. | `SectionRevision` |

The generation prompt also adapts to **delivery mode** (facilitator prompts and group work for instructor-led; direct address and self-checks for self-learning) and adds code-block guidance for technical topics.

## 3. Evidence mapping

```
retrieved page text ──► passages (top 6 by concept overlap) ──► evidence pack [S1] … [Sn]
                                                                │
model: claims {id, text, section_id, source_ids, verbatim excerpt}
                                                                ▼
verify_claims(): unknown IDs removed · metadata-only → Unable to Verify ·
                 excerpt must be found in the FULL retrieved text of a cited evidence source
                                                                ▼
QC Layer 1 claim_reviews ─► final status = most conservative(automated, evaluator)
```

Status rank (weakest support last): Supported < Partially Supported < Unable to Verify < Conflicting Evidence < Unsupported.

Matching: normalise case, whitespace, curly quotes and Markdown punctuation, then exact substring; otherwise a sliding token window must cover ≥ 85% of the excerpt's tokens (tolerates ellipses and minor punctuation). Excerpts under 4 tokens must match exactly.

## 4. Independent evaluators

| | QC Layer 1 | QC Layer 2 |
|---|---|---|
| Route | `POST /qc/factual` | `POST /qc/instructional` |
| Workflow step | `qc_factual` | `qc_instructional` |
| Inputs | lesson, claims with automated statuses, source metadata and passages | objective, objective decomposition, lesson, computed timings, learner profile |
| Does NOT receive | instructional findings | factual report, claim statuses, sources |
| Automated pre-checks | missing citation, quote not found, metadata-only citation, factual section without claims | timing compliance, outcome without question, MCQ structure |
| Rubric | correctness 35, evidence 25, sources 15, consistency 10, completeness 15 | alignment 20, clarity 15, structure 10, examples 15, engagement 10, assessment 15, timing 10, readiness 5 |
| Temperature | 0.1 | 0.2 |

Either layer can fail without affecting the other. Each run is a new `qc_reports` row tied to a version and content hash.

### Scoring
`score_rubric()` clamps each criterion to `[0, max]`, scores any missing criterion as 0 (and says so), and sums. The model cannot produce a score above the rubric or an unexplained number.

### Recommendations
Every non-informational issue (or one with replacement text) becomes a `Recommendation`. **Apply**:
- with `suggested_text` → replaces only that section;
- otherwise → `SectionRevision` prompt for that section only.

The backend writes a new version, stores previous and applied section text, and allows **undo** only if the section is still exactly as applied (otherwise 409, so later edits aren't destroyed).

### Staleness
`stale = report.content_hash != current_version.content_hash`. It is computed on read, so it is always correct after any edit, apply, undo, restore or regeneration. If content returns to an identical state (e.g. undo), the old report becomes fresh again, which is correct because it evaluated exactly that content.

## 5. Limitations

- AI evaluators can miss errors or flag false positives. The scores are rubric-structured assessments, not proof.
- The quote check proves provenance, not entailment.
- Long pages are truncated at 9,000 characters; relevant evidence may be cut.
- The section reviser may change wording more than intended within its section; the version history and undo mitigate this.
- Prompt-injection text inside retrieved web pages could influence the model. Mitigations: evidence is passed as quoted passages, system prompts forbid inventing sources, and outputs are schema-validated and post-processed. This is not a complete defence.
- The default model name (`gemini-3.5-flash`) may be retired by Google; set `GEMINI_MODEL`.
