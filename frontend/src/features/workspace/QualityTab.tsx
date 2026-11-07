import { Check, ChevronDown, Microscope, RotateCcw, ShieldCheck, Undo2, X } from 'lucide-react'
import { useState } from 'react'
import { EvidenceBadge, SeverityBadge } from '../../components/StatusBadges'
import { Alert, Badge, Button, Card, CardHeader, EmptyState, Spinner, cx } from '../../components/ui'
import { errorMessage, useAsync } from '../../hooks/useAsync'
import type { WorkspaceProps } from '../../pages/LessonWorkspace'
import { api } from '../../services/api'
import type { QCReportBody, Recommendation, ReportSummary, Severity } from '../../types/api'
import { formatDateTime, humanize, scoreTone, SEVERITIES } from '../../utils/format'

function RubricTable({ report }: { report: QCReportBody }) {
  return (
    <table className="w-full text-[13px]">
      <caption className="sr-only">Score breakdown by rubric criterion</caption>
      <thead className="text-left text-xs text-muted">
        <tr><th className="py-1.5 font-medium">Criterion</th><th className="py-1.5 text-right font-medium">Score</th></tr>
      </thead>
      <tbody className="divide-y divide-line">
        {report.rubric.map((r) => (
          <tr key={r.criterion}>
            <td className="py-2 pr-3 align-top">
              <p className="font-medium text-ink">{humanize(r.criterion)}</p>
              <p className="text-xs text-muted">{r.rationale}</p>
            </td>
            <td className="whitespace-nowrap py-2 text-right align-top tabular-nums text-ink">
              {r.score}<span className="text-muted"> / {r.max}</span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function ReportPanel({ kind, summary, onRun, running, lessonGenerated }: {
  kind: 'factual' | 'instructional'
  summary: ReportSummary | null
  onRun: () => void
  running: boolean
  lessonGenerated: boolean
}) {
  const [showDetail, setShowDetail] = useState(false)
  const report = summary?.report
  const isFactual = kind === 'factual'
  return (
    <Card className="flex flex-col">
      <CardHeader
        title={<span className="flex items-center gap-2">{isFactual ? <Microscope className="size-4 text-accent" /> : <ShieldCheck className="size-4 text-accent" />}{isFactual ? 'QC Layer 1 · Factual accuracy' : 'QC Layer 2 · Instructional quality'}</span>}
        description={isFactual ? 'Independent fact-check of claims against retrieved evidence.' : 'Independent review of alignment, clarity, activities, assessment and timing.'}
        action={
          <Button size="sm" variant={summary ? 'secondary' : 'primary'} onClick={onRun} loading={running} disabled={!lessonGenerated} icon={<RotateCcw className="size-3.5" />}>
            {summary ? 'Run again' : isFactual ? 'Run Factual Accuracy Check' : 'Run Instructional Quality Check'}
          </Button>
        }
      />
      {!summary ? (
        <EmptyState title="Not run yet">{lessonGenerated ? 'Run this check to get a scored, structured audit.' : 'Generate the lesson first.'}</EmptyState>
      ) : !report ? (
        <Spinner />
      ) : (
        <div className="space-y-4 px-5 py-4">
          {summary.stale && <Alert tone="warn" title="This report is stale">{summary.stale_reason}</Alert>}
          {summary.is_demo && <Alert tone="info">Produced by the offline rule-based demo stand-in, not a live AI evaluator.</Alert>}
          <div className="flex items-end gap-4">
            <p className={cx('font-serif text-5xl tabular-nums', { ok: 'text-ok', warn: 'text-warn', bad: 'text-bad', neutral: 'text-ink', accent: 'text-ink', info: 'text-ink' }[scoreTone(summary.score)])}>
              {summary.score}<span className="text-xl text-muted">/100</span>
            </p>
            <div className="pb-1.5 text-xs text-muted">
              <p>Evaluated version {summary.version_number}</p>
              <p>{formatDateTime(summary.created_at)} · {summary.model}</p>
            </div>
          </div>
          <p className="text-xs italic text-muted">{report.score_disclaimer}</p>
          <p className="text-sm text-ink-2">{report.overall_assessment}</p>
          <div className="flex flex-wrap gap-1.5">
            {SEVERITIES.map((s) => report.severity_counts[s] ? <Badge key={s} tone={s === 'Critical' || s === 'High' ? 'bad' : s === 'Medium' ? 'warn' : 'neutral'}>{report.severity_counts[s]} {s}</Badge> : null)}
          </div>
          {isFactual && report.claim_counts && (
            <dl className="grid grid-cols-3 gap-2 text-center text-xs sm:grid-cols-6">
              {[['Reviewed', report.claims_reviewed], ['Supported', report.claim_counts.supported], ['Partial', report.claim_counts.partially_supported],
                ['Unsupported', report.claim_counts.unsupported], ['Conflicting', report.claim_counts.conflicting_evidence], ['Unverifiable', report.claim_counts.unable_to_verify]].map(([k, v]) => (
                <div key={k as string} className="rounded-lg bg-paper-2 px-2 py-2"><dt className="text-muted">{k}</dt><dd className="font-serif text-lg text-ink">{v as number}</dd></div>
              ))}
            </dl>
          )}
          <button onClick={() => setShowDetail(!showDetail)} aria-expanded={showDetail} className="flex items-center gap-1 text-sm font-medium text-accent">
            <ChevronDown className={cx('size-4 transition-transform', showDetail && 'rotate-180')} /> {showDetail ? 'Hide' : 'Show'} full report
          </button>
          {showDetail && (
            <div className="space-y-5 border-t border-line pt-4">
              <RubricTable report={report} />
              {isFactual && report.claims && (
                <div>
                  <h3 className="mb-2 text-sm font-semibold text-ink">Claim reviews</h3>
                  <ul className="space-y-2 text-[13px]">
                    {report.claims.map((c) => (
                      <li key={c.claim_id} className="rounded-md border border-line p-2.5">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-mono text-xs font-semibold text-accent-2">{c.claim_id}</span>
                          <EvidenceBadge status={c.final_status} />
                          <span className="text-xs text-muted">automated: {c.automated_status} · evaluator: {c.evaluator_status}</span>
                        </div>
                        <p className="mt-1 text-ink">{c.text}</p>
                        <p className="mt-0.5 text-xs text-muted">{c.rationale}</p>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {isFactual && !!report.source_findings?.length && (
                <div>
                  <h3 className="mb-2 text-sm font-semibold text-ink">Source quality</h3>
                  <ul className="space-y-1 text-[13px] text-ink-2">
                    {report.source_findings.map((f) => (
                      <li key={f.source_id}><span className="font-mono text-xs font-semibold text-accent-2">{f.source_id}</span> · authority {f.authority} · {f.is_primary ? 'primary' : 'secondary'}{!f.relevant && ' · not relevant'} — {f.note}</li>
                    ))}
                  </ul>
                </div>
              )}
              {isFactual && !!(report.missing_important_facts?.length || report.suggested_additional_research?.length) && (
                <div className="grid gap-4 text-[13px] sm:grid-cols-2">
                  <div><h3 className="mb-1 text-sm font-semibold text-ink">Missing important facts</h3><ul className="list-disc pl-4 text-ink-2">{report.missing_important_facts?.map((m) => <li key={m}>{m}</li>)}</ul></div>
                  <div><h3 className="mb-1 text-sm font-semibold text-ink">Suggested research</h3><ul className="list-disc pl-4 text-ink-2">{report.suggested_additional_research?.map((m) => <li key={m}>{m}</li>)}</ul></div>
                </div>
              )}
              {!isFactual && report.findings && (
                <div className="space-y-3">
                  {Object.entries(report.findings).map(([area, f]) => (
                    <div key={area} className="text-[13px]">
                      <h3 className="font-semibold text-ink">{humanize(area)}</h3>
                      <p className="text-ink-2">{f.summary}</p>
                      {f.strengths.map((s) => <p key={s} className="text-ok">✓ {s}</p>)}
                      {f.concerns.map((s) => <p key={s} className="text-warn">⚠ {s}</p>)}
                    </div>
                  ))}
                </div>
              )}
              {!isFactual && !!report.outcome_coverage?.length && (
                <div>
                  <h3 className="mb-1 text-sm font-semibold text-ink">Outcome coverage</h3>
                  <ul className="space-y-1 text-[13px]">
                    {report.outcome_coverage.map((o) => (
                      <li key={o.outcome} className={o.covered ? 'text-ink-2' : 'text-bad'}>{o.covered ? '✓' : '✗'} {o.outcome} <span className="text-xs text-muted">{o.where.join(', ')}</span></li>
                    ))}
                  </ul>
                </div>
              )}
              <div>
                <h3 className="mb-2 text-sm font-semibold text-ink">All issues ({report.issues.length})</h3>
                <ul className="space-y-2 text-[13px]">
                  {report.issues.map((i) => (
                    <li key={i.id} className="rounded-md border border-line p-2.5">
                      <div className="flex flex-wrap items-center gap-2"><span className="font-mono text-xs">{i.id}</span><SeverityBadge severity={i.severity} /><Badge>{humanize(i.category)}</Badge>{i.origin === 'automated' && <Badge tone="info">automated check</Badge>}</div>
                      <p className="mt-1 text-ink">{i.explanation}</p>
                      <p className="mt-0.5 text-xs text-muted">{i.evidence_or_reason}</p>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  )
}

function RecommendationCard({ rec, onAction, busy }: { rec: Recommendation; onAction: (action: 'apply' | 'reject' | 'review' | 'undo') => void; busy: string | null }) {
  const done = rec.review_status !== 'pending'
  return (
    <li className={cx('rounded-lg border border-line bg-card p-4', done && 'opacity-80')}>
      <div className="flex flex-wrap items-center gap-2">
        <SeverityBadge severity={rec.severity} />
        <Badge>{rec.qc_type === 'factual' ? 'Layer 1' : 'Layer 2'} · {rec.issue_key}</Badge>
        {rec.affected_section_id ? <Badge tone="accent">Section: {rec.affected_section_id}</Badge> : <Badge>Whole lesson</Badge>}
        {rec.claim_key && <Badge tone="accent">Claim {rec.claim_key}</Badge>}
        {rec.report_stale && rec.review_status === 'pending' && <Badge tone="warn" title={`From the report on version ${rec.report_version_number}`}>from v{rec.report_version_number}</Badge>}
        {done && <Badge tone={rec.review_status === 'accepted' ? 'ok' : rec.review_status === 'rejected' ? 'bad' : 'neutral'}>{humanize(rec.review_status)}</Badge>}
      </div>
      <dl className="mt-2 space-y-1.5 text-[13px]">
        <div><dt className="sr-only">Issue</dt><dd className="font-medium text-ink">{rec.issue}</dd></div>
        {rec.why_it_matters && <div><dt className="inline text-muted">Why it matters: </dt><dd className="inline text-ink-2">{rec.why_it_matters}</dd></div>}
        <div><dt className="inline text-muted">Suggested improvement: </dt><dd className="inline text-ink-2">{rec.suggested_change}</dd></div>
      </dl>
      {rec.suggested_text && (
        <details className="mt-2 text-[13px]">
          <summary className="cursor-pointer text-accent">Suggested revised text</summary>
          <pre className="mt-1 whitespace-pre-wrap rounded bg-paper-2 p-2 font-sans text-ink-2">{rec.suggested_text}</pre>
        </details>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        {rec.review_status === 'pending' || rec.review_status === 'reviewed' || rec.review_status === 'undone' ? (
          <>
            {rec.affected_section_id && (
              <Button size="sm" variant="primary" loading={busy === 'apply'} onClick={() => onAction('apply')} icon={<Check className="size-3.5" />}
                title={rec.suggested_text ? 'Replace the section with the suggested text' : 'Ask the AI to revise only this section'}>
                Accept & apply
              </Button>
            )}
            {rec.review_status !== 'reviewed' && <Button size="sm" loading={busy === 'review'} onClick={() => onAction('review')}>Mark as reviewed</Button>}
            <Button size="sm" variant="ghost" loading={busy === 'reject'} onClick={() => onAction('reject')} icon={<X className="size-3.5" />}>Reject</Button>
          </>
        ) : rec.can_undo ? (
          <Button size="sm" loading={busy === 'undo'} onClick={() => onAction('undo')} icon={<Undo2 className="size-3.5" />}>Undo change</Button>
        ) : null}
      </div>
    </li>
  )
}

export default function QualityTab({ lesson, setLesson, pipeline }: WorkspaceProps) {
  const reports = useAsync(() => api.reports(lesson.id), [lesson.id, lesson.latest_reports.factual?.id, lesson.latest_reports.instructional?.id, lesson.current_version?.content_hash])
  const recs = useAsync(() => api.recommendations(lesson.id), [lesson.id, lesson.latest_reports.factual?.id, lesson.latest_reports.instructional?.id, lesson.current_version?.id])
  const [busy, setBusy] = useState<{ id: number; action: string } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [filter, setFilter] = useState<'open' | 'all'>('open')
  const [severity, setSeverity] = useState<Severity | 'all'>('all')

  const full = (kind: 'factual' | 'instructional') => {
    const latestId = lesson.latest_reports[kind]?.id
    return reports.data?.reports.find((r) => r.id === latestId) ?? (latestId ? lesson.latest_reports[kind] : null)
  }

  const act = async (rec: Recommendation, action: 'apply' | 'reject' | 'review' | 'undo') => {
    setBusy({ id: rec.id, action })
    setError(null)
    setNotice(null)
    try {
      if (action === 'apply') {
        const r = await api.applyRecommendation(lesson.id, rec.id)
        setLesson(r.lesson)
        setNotice(`Applied to section “${r.result.section_id}” as version ${r.result.version_number}. ${r.result.change_summary} QC reports are now stale; rerun them to check the change.`)
      } else if (action === 'undo') {
        setLesson((await api.undoRecommendation(lesson.id, rec.id)).lesson)
        setNotice('Change undone as a new version.')
      } else if (action === 'reject') {
        await api.rejectRecommendation(lesson.id, rec.id)
      } else {
        await api.reviewRecommendation(lesson.id, rec.id)
      }
      await recs.reload()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(null)
    }
  }

  const all = (recs.data?.recommendations ?? []).filter((r) => r.from_latest_report || r.review_status === 'accepted')
  const shown = all
    .filter((r) => (filter === 'open' ? ['pending', 'reviewed', 'undone'].includes(r.review_status) : true))
    .filter((r) => severity === 'all' || r.severity === severity)
    .sort((a, b) => SEVERITIES.indexOf(a.severity) - SEVERITIES.indexOf(b.severity))
  const generated = !!lesson.current_version

  return (
    <div className="space-y-6">
      <p className="text-sm text-muted">
        The two checks run separately with different instructions and rubrics. Either can be rerun on its own, and a failure in one never blocks the other.
      </p>
      {pipeline.error && (pipeline.error.stage === 'qc_factual' || pipeline.error.stage === 'qc_instructional') && (
        <Alert tone="bad" title={`${pipeline.error.stage === 'qc_factual' ? 'Factual' : 'Instructional'} check failed`}>{pipeline.error.message}</Alert>
      )}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <ReportPanel kind="factual" summary={full('factual') ?? null} lessonGenerated={generated} running={pipeline.running === 'qc_factual'} onRun={() => void pipeline.runStage('qc_factual')} />
        <ReportPanel kind="instructional" summary={full('instructional') ?? null} lessonGenerated={generated} running={pipeline.running === 'qc_instructional'} onRun={() => void pipeline.runStage('qc_instructional')} />
      </div>

      <Card>
        <CardHeader
          title="Recommendations"
          description="Accepting applies the change to one section only and saves a new version. Nothing is overwritten silently."
          action={
            <div className="flex gap-2">
              <select aria-label="Filter by severity" value={severity} onChange={(e) => setSeverity(e.target.value as Severity | 'all')} className="h-8 rounded-md border border-line bg-card px-2 text-xs">
                <option value="all">All severities</option>
                {SEVERITIES.map((s) => <option key={s}>{s}</option>)}
              </select>
              <div className="flex rounded-md border border-line p-0.5 text-xs" role="group" aria-label="Recommendation status filter">
                {(['open', 'all'] as const).map((f) => (
                  <button key={f} onClick={() => setFilter(f)} aria-pressed={filter === f} className={cx('rounded px-2.5 py-1', filter === f ? 'bg-ink text-paper' : 'text-ink-2')}>
                    {f === 'open' ? 'Open' : 'All'}
                  </button>
                ))}
              </div>
            </div>
          }
        />
        <div className="space-y-3 p-5">
          {error && <Alert tone="bad">{error}</Alert>}
          {notice && <Alert tone="ok">{notice}</Alert>}
          {recs.loading && !recs.data ? <Spinner /> : shown.length === 0 ? (
            <EmptyState title={all.length ? 'Nothing open' : 'No recommendations'}>
              {all.length ? 'Every recommendation has been accepted, rejected or reviewed.' : 'Recommendations appear after a quality check finds issues.'}
            </EmptyState>
          ) : (
            <ul className="space-y-3">
              {shown.map((r) => <RecommendationCard key={r.id} rec={r} busy={busy?.id === r.id ? busy.action : null} onAction={(a) => void act(r, a)} />)}
            </ul>
          )}
        </div>
      </Card>
    </div>
  )
}
