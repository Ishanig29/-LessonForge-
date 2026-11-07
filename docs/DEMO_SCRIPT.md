# Demo script (about 4 minutes)

**Setup before recording:** backend running with real keys (`python run.py`), or with `DEMO_MODE=true` if keys aren't available (say so on camera). Frontend at `localhost:5173`. Start with an empty or tidy database.

---

### 0:00 – 0:20 · The problem
> "AI can write a lesson in seconds, but you can't tell which facts are real, references are often invented, and nothing enforces a time limit. LessonForge researches first, ties every key claim to retrieved evidence, enforces 45 minutes in code, and has two independent reviewers check the result."

Show the **Dashboard**: counts come from the database, and the empty state is shown when there are no lessons.

### 0:20 – 0:45 · Create
1. **Create Lesson** → click the *HTTP Requests and Responses* example.
2. Point out that the objective text is kept verbatim, plus the optional audience, difficulty and delivery mode.
3. (Optional) Clear the title and click Generate to show friendly validation.
4. **Generate lesson**.

### 0:45 – 1:30 · Real workflow
On **Overview**, watch the steps change from Pending → Running → Completed. Each status is a database record.
- Objective analysis: original objective vs AI interpretation, measurable LO1–LO3.
- Research summary: N sources, how many usable as evidence, duplicates removed.
- Timing: "45 minutes, after 1 shortening round" if it happens. Explain: "The backend summed the sections, found the lesson too long, asked the AI to shorten only the longest sections, and validated again."
- 45-minute plan bar: the totals are the sum of the sections.

### 1:30 – 2:15 · Traceability (signature feature)
**Research** tab:
- Provider cards: web OK; if books or videos failed, show the honest error and the **Retry** button.
- **Evidence traceability**: open **C3** ("GET, HEAD, OPTIONS and TRACE are safe"). Show the verbatim excerpt, the RFC 9110 source and its retrieved passages.
- Filter **Unsupported**: show the claim with no source. "The system doesn't hide this; it flags it."
- Explain: "Every excerpt is checked against the actual retrieved text. If the model invents a quote, the claim becomes *Unable to Verify*. Books and videos are metadata only, so they can never prove a claim."
- Source cards: tier and the written "why this rating".

### 2:15 – 3:00 · Two independent QC layers
**Quality Control** tab:
- Two separate panels, buttons and rubrics. Open **Show full report** on Layer 1: rubric rows, per-claim automated vs evaluator vs final status, source findings.
- Layer 2: outcome coverage, timing finding.
- "Scores are summed by the backend from clamped rubric criteria, and the report says it's an assessment, not a guarantee."
- **Accept & apply** a recommendation, then show the notice: one section changed, new version, both reports now **STALE**.
- Click **Run again** on both.

### 3:00 – 3:30 · Edit, autosave, versions
**Lesson Content**: change a section title, then point to *Saving… → Saved*. Refresh the page and the change is still there. Show **Save as named version**. In **Export → Version history**, show generated / recommendation / instructor-edit versions and **Restore**.

### 3:30 – 4:00 · Finalize and export
**Final Preview**: learner-facing layout, timing table, clickable claim markers, videos (labelled "transcripts not reviewed"), references with evidence-use labels. **Finalize** (if a report is stale, the warning dialog appears).
**Export → Download ZIP**: open the README manifest showing the version, FINALIZED status and QC freshness per report.

> "Everything is local, keys stay on the backend, and nothing is presented as more certain than it is."

---

**If asked about demo mode:** "Without keys, demo mode uses real RFC/MDN/PostgreSQL text captured from their GitHub repos and a rule-based stand-in that labels itself everywhere and scores criteria it can't judge as zero. No books or videos are faked."
