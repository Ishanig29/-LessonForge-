import { AlertCircle, Check, ChevronDown, Eye, Loader2, Pencil, Plus, Save, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { LessonMarkdown } from '../../components/LessonMarkdown'
import { Alert, Badge, Button, Card, CardHeader, EmptyState, Field, Modal, Select, TextArea, TextInput, cx } from '../../components/ui'
import { errorMessage, useAsync } from '../../hooks/useAsync'
import { useAutosave, type SaveState } from '../../hooks/useAutosave'
import type { WorkspaceProps } from '../../pages/LessonWorkspace'
import { api, ApiError } from '../../services/api'
import type { KnowledgeCheckQuestion, LessonContent, LessonSection } from '../../types/api'
import { humanize, relativeTime } from '../../utils/format'

function SaveIndicator({ state, error, onRetry }: { state: SaveState; error: string | null; onRetry: () => void }) {
  if (state === 'saving') return <span className="flex items-center gap-1.5 text-xs text-muted" role="status"><Loader2 className="size-3.5 animate-spin" /> Saving…</span>
  if (state === 'saved') return <span className="flex items-center gap-1.5 text-xs text-ok" role="status"><Check className="size-3.5" /> Saved</span>
  if (state === 'dirty') return <span className="text-xs text-muted" role="status">Unsaved changes</span>
  if (state === 'error')
    return (
      <span className="flex items-center gap-1.5 text-xs text-bad" role="alert">
        <AlertCircle className="size-3.5" /> Save failed{error ? `: ${error}` : ''}
        <button onClick={onRetry} className="underline">Retry</button>
      </span>
    )
  return null
}

function SectionEditor({ section, onChange, open, onToggle }: { section: LessonSection; onChange: (s: LessonSection) => void; open: boolean; onToggle: () => void }) {
  const [preview, setPreview] = useState(false)
  return (
    <Card as="article" className="overflow-hidden">
      <button onClick={onToggle} aria-expanded={open} className="flex w-full items-center gap-3 px-5 py-3.5 text-left hover:bg-paper/50">
        <Badge>{humanize(section.kind)}</Badge>
        <span className="min-w-0 flex-1 truncate font-medium text-ink">{section.title}</span>
        <span className="text-sm tabular-nums text-muted">{section.duration_minutes} min</span>
        <ChevronDown className={cx('size-4 text-muted transition-transform', open && 'rotate-180')} aria-hidden />
      </button>
      {open && (
        <div className="space-y-4 border-t border-line px-5 py-4">
          <div className="grid gap-4 sm:grid-cols-[1fr_120px]">
            <Field label="Section title" required>
              {(p) => <TextInput id={p.id} value={section.title} onChange={(e) => onChange({ ...section, title: e.target.value })} />}
            </Field>
            <Field label="Minutes" required>
              {(p) => (
                <TextInput id={p.id} type="number" min={0} max={45} value={section.duration_minutes}
                  onChange={(e) => onChange({ ...section, duration_minutes: Math.max(0, Math.min(45, Number(e.target.value) || 0)) })} />
              )}
            </Field>
          </div>
          <Field label="Teaching / learning activity" required>
            {(p) => <TextInput id={p.id} value={section.activity} onChange={(e) => onChange({ ...section, activity: e.target.value })} />}
          </Field>
          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <span className="text-[13px] font-medium text-ink">Content <span className="font-normal text-muted">(Markdown; keep [C1]-style claim markers next to claims)</span></span>
              <div className="flex rounded-md border border-line p-0.5 text-xs" role="group" aria-label="Editor mode">
                <button onClick={() => setPreview(false)} aria-pressed={!preview} className={cx('flex items-center gap-1 rounded px-2 py-0.5', !preview && 'bg-ink text-paper')}><Pencil className="size-3" /> Edit</button>
                <button onClick={() => setPreview(true)} aria-pressed={preview} className={cx('flex items-center gap-1 rounded px-2 py-0.5', preview && 'bg-ink text-paper')}><Eye className="size-3" /> Preview</button>
              </div>
            </div>
            {preview ? (
              <div className="min-h-32 rounded-lg border border-line bg-paper/40 px-4 py-3"><LessonMarkdown>{section.content}</LessonMarkdown></div>
            ) : (
              <TextArea aria-label={`Content of ${section.title}`} rows={Math.min(24, Math.max(6, section.content.split('\n').length + 1))} className="font-mono text-[13px]"
                value={section.content} onChange={(e) => onChange({ ...section, content: e.target.value })} />
            )}
          </div>
        </div>
      )}
    </Card>
  )
}

function QuestionEditor({ q, onChange, onRemove }: { q: KnowledgeCheckQuestion; onChange: (q: KnowledgeCheckQuestion) => void; onRemove: () => void }) {
  return (
    <div className="space-y-3 rounded-lg border border-line bg-card p-4">
      <div className="flex items-center gap-2">
        <span className="font-mono text-xs font-semibold text-accent-2">{q.id}</span>
        <Select aria-label="Question type" value={q.kind} onChange={(e) => onChange({ ...q, kind: e.target.value as KnowledgeCheckQuestion['kind'] })} className="h-8 w-44 text-xs">
          <option value="multiple_choice">Multiple choice</option>
          <option value="short_answer">Short answer</option>
          <option value="practical">Practical</option>
        </Select>
        <TextInput aria-label="Outcomes measured" className="h-8 w-40 text-xs" placeholder="LO1, LO2" value={q.outcome_ids.join(', ')}
          onChange={(e) => onChange({ ...q, outcome_ids: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })} />
        <Button size="sm" variant="ghost" className="ml-auto" onClick={onRemove} aria-label={`Remove ${q.id}`} icon={<Trash2 className="size-3.5 text-bad" />} />
      </div>
      <TextArea aria-label="Question" rows={2} value={q.question} onChange={(e) => onChange({ ...q, question: e.target.value })} />
      {q.kind === 'multiple_choice' && (
        <TextArea aria-label="Options, one per line" rows={4} placeholder="One option per line" value={q.options.join('\n')}
          onChange={(e) => onChange({ ...q, options: e.target.value.split('\n') })} />
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        <TextArea aria-label="Answer" rows={2} placeholder="Correct answer" value={q.answer} onChange={(e) => onChange({ ...q, answer: e.target.value })} />
        <TextArea aria-label="Explanation" rows={2} placeholder="Why this is correct" value={q.explanation} onChange={(e) => onChange({ ...q, explanation: e.target.value })} />
      </div>
    </div>
  )
}

export default function ContentTab({ lesson, setLesson, goTo }: WorkspaceProps) {
  const version = lesson.current_version
  const serverKey = version ? `${version.id}:${version.updated_at}` : ''
  const [draft, setDraft] = useState<LessonContent | null>(version?.content ?? null)
  const syncedKey = useRef(serverKey)
  const [openSection, setOpenSection] = useState<string | null>(null)
  const [snapshotOpen, setSnapshotOpen] = useState(false)
  const [snapshotNote, setSnapshotNote] = useState('')
  const [snapshotBusy, setSnapshotBusy] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)
  const sources = useAsync(() => api.sources(lesson.id), [lesson.id, lesson.source_count])

  const save = useCallback(
    async (value: LessonContent) => {
      try {
        const res = await api.saveContent(lesson.id, value, { autosave: true })
        syncedKey.current = `${res.lesson.current_version!.id}:${res.lesson.current_version!.updated_at}`
        setLesson(res.lesson)
        setValidationError(null)
      } catch (e) {
        if (e instanceof ApiError && e.status === 422) {
          const d = Array.isArray(e.details) ? (e.details as { loc?: string; msg?: string; field?: string; message?: string }[]).map((x) => `${x.loc ?? x.field}: ${x.msg ?? x.message}`).join('; ') : ''
          setValidationError(`${e.message} ${d}`)
        }
        throw e
      }
    },
    [lesson.id, setLesson],
  )
  const autosave = useAutosave<LessonContent>({ save, storageKey: `lessonforge:draft:${lesson.id}` })
  const [recoverable, setRecoverable] = useState(() => {
    const d = autosave.readDraft()
    return d && version && JSON.stringify(d.value) !== JSON.stringify(version.content) ? d : null
  })

  // Adopt server changes (e.g. an applied recommendation) unless the user has unsaved edits.
  useEffect(() => {
    if (serverKey !== syncedKey.current && !autosave.hasPending()) {
      syncedKey.current = serverKey
      setDraft(version?.content ?? null)
    }
  }, [serverKey, version, autosave])

  const update = (fn: (d: LessonContent) => LessonContent) => {
    setDraft((d) => {
      if (!d) return d
      const next = fn(d)
      autosave.schedule(next)
      return next
    })
  }

  const total = useMemo(() => draft?.sections.reduce((a, s) => a + (s.duration_minutes || 0), 0) ?? 0, [draft])
  const sourceMap = useMemo(() => Object.fromEntries((sources.data?.sources ?? []).map((s) => [s.source_id, s])), [sources.data])

  if (!draft || !version) {
    return (
      <Card>
        <EmptyState title="Nothing to edit yet" action={<Button onClick={() => goTo('overview')}>Go to workflow</Button>}>
          Generate the lesson first. Your edits will be autosaved and versioned.
        </EmptyState>
      </Card>
    )
  }

  const snapshot = async () => {
    setSnapshotBusy(true)
    try {
      await autosave.flush()
      const res = await api.saveContent(lesson.id, draft, { createVersion: true, description: snapshotNote.trim() || 'Saved version' })
      syncedKey.current = `${res.lesson.current_version!.id}:${res.lesson.current_version!.updated_at}`
      setLesson(res.lesson)
      autosave.discardDraft()
      setSnapshotOpen(false)
      setSnapshotNote('')
    } catch (e) {
      setValidationError(errorMessage(e))
    } finally {
      setSnapshotBusy(false)
    }
  }

  const unusedSources = (sources.data?.sources ?? []).filter((s) => !draft.reference_ids.includes(s.source_id) && s.source_type !== 'youtube')

  return (
    <div className="space-y-5">
      <div className="sticky top-0 z-10 -mx-1 flex flex-wrap items-center gap-3 rounded-lg border border-line bg-paper/95 px-4 py-2.5 backdrop-blur">
        <span className="text-sm text-ink-2">Editing version {version.version_number}</span>
        <Badge tone={total <= 45 ? 'neutral' : 'bad'}>{total} / 45 min</Badge>
        <SaveIndicator state={autosave.state} error={autosave.lastError} onRetry={() => void autosave.flush()} />
        <Button size="sm" className="ml-auto" onClick={() => setSnapshotOpen(true)} icon={<Save className="size-3.5" />}>Save as named version</Button>
      </div>

      {recoverable && (
        <Alert tone="warn" title="Unsaved changes found"
          action={
            <div className="flex gap-2">
              <Button size="sm" variant="primary" onClick={() => { setDraft(recoverable.value); autosave.schedule(recoverable.value); setRecoverable(null) }}>Restore</Button>
              <Button size="sm" variant="ghost" onClick={() => { autosave.discardDraft(); setRecoverable(null) }}>Discard</Button>
            </div>
          }>
          This browser kept edits from {relativeTime(new Date(recoverable.savedAt).toISOString())} that were not saved to the server.
        </Alert>
      )}
      {validationError && <Alert tone="bad" title="Not saved">{validationError}</Alert>}
      {total > 45 && <Alert tone="bad">Sections add up to {total} minutes. Lessons must fit in 45 minutes, and this one cannot be finalized until it does.</Alert>}
      {(lesson.latest_reports.factual || lesson.latest_reports.instructional) && (
        <p className="text-xs text-muted">Saving changes marks earlier QC reports as stale until you rerun them.</p>
      )}

      <Card>
        <CardHeader title="Lesson details" />
        <div className="grid gap-4 px-5 py-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Field label="Lesson title" required>
              {(p) => <TextInput id={p.id} value={draft.title} onChange={(e) => update((d) => ({ ...d, title: e.target.value }))} />}
            </Field>
          </div>
          <div className="sm:col-span-2">
            <Field label="Learning objective" required hint="The original objective is preserved in the objective analysis.">
              {(p) => <TextArea id={p.id} aria-describedby={p.describedBy} rows={2} value={draft.learning_objective} onChange={(e) => update((d) => ({ ...d, learning_objective: e.target.value }))} />}
            </Field>
          </div>
          <div className="sm:col-span-2">
            <Field label="Expected learning outcomes" required hint="One outcome per line.">
              {(p) => <TextArea id={p.id} aria-describedby={p.describedBy} rows={3} value={draft.learning_outcomes.join('\n')} onChange={(e) => update((d) => ({ ...d, learning_outcomes: e.target.value.split('\n') }))} />}
            </Field>
          </div>
          <Field label="Target audience" required>
            {(p) => <TextInput id={p.id} value={draft.target_audience} onChange={(e) => update((d) => ({ ...d, target_audience: e.target.value }))} />}
          </Field>
          <Field label="Assumed knowledge" required>
            {(p) => <TextInput id={p.id} value={draft.assumed_knowledge} onChange={(e) => update((d) => ({ ...d, assumed_knowledge: e.target.value }))} />}
          </Field>
        </div>
      </Card>

      <section aria-label="Lesson sections" className="space-y-2">
        <h2 className="px-1 text-sm font-semibold text-ink">Sections</h2>
        {draft.sections.map((s, i) => (
          <SectionEditor key={s.id} section={s} open={openSection === s.id} onToggle={() => setOpenSection(openSection === s.id ? null : s.id)}
            onChange={(ns) => update((d) => ({ ...d, sections: d.sections.map((x, j) => (j === i ? ns : x)) }))} />
        ))}
      </section>

      <Card>
        <CardHeader title="Knowledge check" description="Questions, answers and explanations. Map each question to the outcomes it measures."
          action={<Button size="sm" icon={<Plus className="size-3.5" />} onClick={() => update((d) => {
            const n = Math.max(0, ...d.knowledge_check.map((q) => Number(q.id.slice(1)) || 0)) + 1
            return { ...d, knowledge_check: [...d.knowledge_check, { id: `Q${n}`, question: 'New question?', kind: 'short_answer', options: [], answer: 'Answer', explanation: 'Explain the answer.', outcome_ids: [] }] }
          })}>Add question</Button>} />
        <div className="space-y-3 p-5">
          {draft.knowledge_check.map((q, i) => (
            <QuestionEditor key={q.id} q={q}
              onChange={(nq) => update((d) => ({ ...d, knowledge_check: d.knowledge_check.map((x, j) => (j === i ? nq : x)) }))}
              onRemove={() => update((d) => ({ ...d, knowledge_check: d.knowledge_check.filter((_, j) => j !== i) }))} />
          ))}
        </div>
      </Card>

      <Card>
        <CardHeader title="References" description="Only sources collected by research can be referenced; nothing can be typed in freehand." />
        <ul className="divide-y divide-line">
          {draft.reference_ids.map((id) => (
            <li key={id} className="flex items-center gap-3 px-5 py-2.5 text-sm">
              <span className="font-mono text-xs font-semibold text-accent-2">{id}</span>
              <span className="min-w-0 flex-1 truncate text-ink-2">{sourceMap[id]?.title ?? id}</span>
              <Button size="sm" variant="ghost" aria-label={`Remove reference ${id}`} icon={<Trash2 className="size-3.5" />}
                onClick={() => update((d) => ({ ...d, reference_ids: d.reference_ids.filter((x) => x !== id) }))} />
            </li>
          ))}
        </ul>
        {unusedSources.length > 0 && (
          <div className="border-t border-line px-5 py-3">
            <Select aria-label="Add a reference from collected sources" value="" onChange={(e) => e.target.value && update((d) => ({ ...d, reference_ids: [...d.reference_ids, e.target.value] }))}>
              <option value="">Add a collected source…</option>
              {unusedSources.map((s) => <option key={s.source_id} value={s.source_id}>{s.source_id} · {s.title}</option>)}
            </Select>
          </div>
        )}
      </Card>

      <Modal open={snapshotOpen} title="Save as named version" onClose={() => setSnapshotOpen(false)}
        footer={<><Button variant="ghost" onClick={() => setSnapshotOpen(false)}>Cancel</Button><Button variant="primary" loading={snapshotBusy} onClick={() => void snapshot()}>Save version</Button></>}>
        <Field label="What changed?">
          {(p) => <TextInput id={p.id} value={snapshotNote} onChange={(e) => setSnapshotNote(e.target.value)} placeholder="e.g. Simplified the status-code table" autoFocus />}
        </Field>
        <p className="mt-2 text-xs text-muted">Autosave keeps your work safe; a named version is a checkpoint you can restore later.</p>
      </Modal>
    </div>
  )
}
