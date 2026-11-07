import { BadgeCheck, Clock, PlayCircle } from 'lucide-react'
import { useState } from 'react'
import { LessonMarkdown } from '../../components/LessonMarkdown'
import { Alert, Badge, Button, Card, ConfirmDialog, EmptyState } from '../../components/ui'
import { errorMessage, useAsync } from '../../hooks/useAsync'
import type { WorkspaceProps } from '../../pages/LessonWorkspace'
import { api, ApiError } from '../../services/api'
import { humanize } from '../../utils/format'

export default function PreviewTab({ lesson, setLesson, goTo }: WorkspaceProps) {
  const content = lesson.current_version?.content
  const sources = useAsync(() => api.sources(lesson.id), [lesson.id, lesson.source_count])
  const [busy, setBusy] = useState(false)
  const [warnings, setWarnings] = useState<string[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  if (!content || !lesson.timing) {
    return <Card><EmptyState title="Nothing to preview yet">Generate the lesson to see the learner-facing version.</EmptyState></Card>
  }
  const byKey = Object.fromEntries((sources.data?.sources ?? []).map((s) => [s.source_id, s]))

  const finalize = async (acknowledge: boolean) => {
    setBusy(true)
    setError(null)
    try {
      setLesson(await api.finalize(lesson.id, acknowledge))
      setWarnings(null)
    } catch (e) {
      if (e instanceof ApiError && e.code === 'warnings_require_acknowledgement') {
        setWarnings((e.details as { warnings: string[] }).warnings)
      } else {
        setError(errorMessage(e))
      }
    } finally {
      setBusy(false)
    }
  }

  const reports = [lesson.latest_reports.factual, lesson.latest_reports.instructional]
  return (
    <div className="space-y-5">
      <Card className="flex flex-wrap items-center gap-3 px-5 py-3.5">
        {lesson.is_current_finalized ? (
          <p className="flex items-center gap-2 text-sm font-medium text-ok"><BadgeCheck className="size-4" /> Version {lesson.current_version!.version_number} is finalized.</p>
        ) : (
          <p className="text-sm text-ink-2">Draft · version {lesson.current_version!.version_number}. Review below, then finalize.</p>
        )}
        {reports.some((r) => !r) && <Badge tone="warn">A QC check has not been run</Badge>}
        {reports.some((r) => r?.stale) && <Badge tone="warn">A QC report is stale</Badge>}
        {!lesson.is_current_finalized && (
          <Button className="ml-auto" variant="primary" loading={busy} disabled={!lesson.timing.compliant} onClick={() => void finalize(false)}
            title={lesson.timing.compliant ? undefined : 'The lesson exceeds 45 minutes'}>
            Finalize this version
          </Button>
        )}
      </Card>
      {error && <Alert tone="bad">{error}</Alert>}

      <article className="rounded-xl border border-line bg-card px-6 py-8 shadow-soft sm:px-10">
        <header className="border-b border-line pb-6">
          <p className="text-xs font-medium uppercase tracking-wider text-accent">{lesson.difficulty} · {lesson.delivery_mode}</p>
          <h1 className="mt-2 font-serif text-3xl text-ink">{content.title}</h1>
          <p className="mt-3 text-ink-2"><span className="font-medium text-ink">Objective: </span>{content.learning_objective}</p>
          <div className="mt-4 grid gap-4 text-sm sm:grid-cols-2">
            <div>
              <p className="font-medium text-ink">By the end you will be able to</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-5 text-ink-2">{content.learning_outcomes.filter(Boolean).map((o) => <li key={o}>{o}</li>)}</ul>
            </div>
            <div className="space-y-2 text-ink-2">
              <p><span className="font-medium text-ink">For: </span>{content.target_audience}</p>
              <p><span className="font-medium text-ink">You should already know: </span>{content.assumed_knowledge}</p>
              <p className="flex items-center gap-1.5"><Clock className="size-4 text-muted" /> {lesson.timing.total_minutes} minutes</p>
            </div>
          </div>
        </header>

        <section className="border-b border-line py-6" aria-label="Lesson plan">
          <h2 className="mb-3 font-serif text-xl text-ink">Lesson plan</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wide text-muted"><tr><th className="py-1.5">Section</th><th className="py-1.5">Activity</th><th className="py-1.5 text-right">Minutes</th></tr></thead>
              <tbody className="divide-y divide-line">
                {content.sections.map((s) => (
                  <tr key={s.id}><td className="py-2 pr-4 text-ink">{s.title}</td><td className="py-2 pr-4 text-ink-2">{s.activity}</td><td className="py-2 text-right tabular-nums">{s.duration_minutes}</td></tr>
                ))}
                <tr className="font-semibold"><td className="py-2">Total</td><td /><td className="py-2 text-right tabular-nums">{lesson.timing.total_minutes}</td></tr>
              </tbody>
            </table>
          </div>
        </section>

        {content.sections.map((s) => (
          <section key={s.id} className="border-b border-line py-6 last:border-0" aria-labelledby={`sec-${s.id}`}>
            <div className="mb-2 flex flex-wrap items-baseline gap-2">
              <h2 id={`sec-${s.id}`} className="font-serif text-xl text-ink">{s.title}</h2>
              <span className="text-xs text-muted">{s.duration_minutes} min · {humanize(s.kind)}</span>
            </div>
            {s.activity && <p className="mb-3 rounded-md bg-accent-soft px-3 py-1.5 text-[13px] text-accent-2">{s.activity}</p>}
            <LessonMarkdown onClaimClick={(id) => goTo('research', id)}>{s.content}</LessonMarkdown>
            {s.kind === 'knowledge_check' && (
              <ol className="mt-4 space-y-3 text-sm">
                {content.knowledge_check.map((q) => (
                  <li key={q.id}>
                    <p className="font-medium text-ink">{q.id}. {q.question}</p>
                    {q.options.length > 0 && <ol className="mt-1 list-[upper-alpha] pl-6 text-ink-2">{q.options.filter(Boolean).map((o) => <li key={o}>{o}</li>)}</ol>}
                  </li>
                ))}
              </ol>
            )}
            {s.kind === 'answers' && (
              <dl className="mt-4 space-y-3 text-sm">
                {content.knowledge_check.map((q) => (
                  <div key={q.id}>
                    <dt className="font-medium text-ink">{q.id}: {q.answer} {q.outcome_ids.length > 0 && <span className="text-xs font-normal text-muted">(measures {q.outcome_ids.join(', ')})</span>}</dt>
                    <dd className="text-ink-2">{q.explanation}</dd>
                  </div>
                ))}
              </dl>
            )}
          </section>
        ))}

        <section className="border-t border-line py-6" aria-label="Supplementary videos">
          <h2 className="mb-1 font-serif text-xl text-ink">Supplementary videos</h2>
          <p className="mb-3 text-xs text-muted">Found via YouTube search metadata. Transcripts were not reviewed, so watch before assigning.</p>
          {content.supplementary_video_ids.length === 0 ? <p className="text-sm text-muted">No videos were retrieved for this lesson.</p> : (
            <ul className="space-y-2 text-sm">
              {content.supplementary_video_ids.map((k) => byKey[k] && (
                <li key={k} className="flex items-center gap-2"><PlayCircle className="size-4 text-muted" /><a href={byKey[k].url ?? '#'} target="_blank" rel="noreferrer noopener" className="text-accent hover:underline">{byKey[k].title}</a><span className="text-xs text-muted">{byKey[k].author_or_domain}</span></li>
              ))}
            </ul>
          )}
        </section>

        <section className="border-t border-line pt-6" aria-label="References">
          <h2 className="mb-3 font-serif text-xl text-ink">References</h2>
          <ol className="space-y-2 text-sm">
            {content.reference_ids.map((k) => {
              const s = byKey[k]
              if (!s) return null
              return (
                <li key={k} className="text-ink-2">
                  <span className="font-mono text-xs font-semibold text-accent-2">[{k}]</span> {s.title}. {s.author_or_domain}
                  {s.published_date && `, ${String(s.published_date).slice(0, 10)}`}.{' '}
                  {s.url && <a href={s.url} target="_blank" rel="noreferrer noopener" className="break-all text-accent hover:underline">{s.url}</a>}{' '}
                  <span className="text-xs text-muted">({s.evidence_use === 'evidence' ? 'used as evidence' : s.evidence_use === 'further_reading' ? 'further reading, metadata only' : 'supplementary'}{s.is_demo ? ', demo fixture' : ''})</span>
                </li>
              )
            })}
          </ol>
        </section>
      </article>

      <ConfirmDialog open={!!warnings} title="Finalize with warnings?" confirmLabel="Finalize anyway" loading={busy} onCancel={() => setWarnings(null)} onConfirm={() => void finalize(true)}>
        <ul className="list-disc space-y-1 pl-5">{warnings?.map((w) => <li key={w}>{w}</li>)}</ul>
        <p className="mt-3">These warnings will be recorded with the finalized version and printed in exports.</p>
      </ConfirmDialog>
    </div>
  )
}
