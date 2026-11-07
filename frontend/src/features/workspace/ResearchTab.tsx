import { ChevronDown, Flag, RotateCw } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { EvidenceBadge } from '../../components/StatusBadges'
import { SourceCard } from '../../components/SourceCard'
import { Alert, Badge, Button, Card, CardHeader, EmptyState, Spinner, cx } from '../../components/ui'
import { errorMessage, useAsync } from '../../hooks/useAsync'
import type { WorkspaceProps } from '../../pages/LessonWorkspace'
import { api } from '../../services/api'
import type { ClaimWithSources, EvidenceStatus, ProviderReport, ResearchResult, SourceType } from '../../types/api'

const PROVIDER_LABEL: Record<string, string> = { tavily: 'Web (Tavily)', google_books: 'Books (Google Books)', youtube: 'Videos (YouTube)' }
const STATUS_FILTERS: (EvidenceStatus | 'all' | 'flagged')[] = ['all', 'Supported', 'Partially Supported', 'Unsupported', 'Unable to Verify', 'Conflicting Evidence', 'flagged']

function ProviderStatus({ report, onRetry, busy }: { report: ProviderReport; onRetry: () => void; busy: boolean }) {
  const tone = report.status === 'ok' ? 'ok' : report.status === 'failed' ? 'bad' : 'warn'
  return (
    <div className="rounded-lg border border-line bg-card px-3 py-2.5 text-[13px]">
      <div className="flex items-center gap-2">
        <span className="font-medium text-ink">{PROVIDER_LABEL[report.provider]}</span>
        <Badge tone={tone}>{report.status === 'ok' ? `${report.found} results` : report.status}</Badge>
        {report.status !== 'ok' && (
          <Button size="sm" variant="ghost" className="ml-auto" onClick={onRetry} loading={busy} icon={<RotateCw className="size-3.5" />}>Retry</Button>
        )}
      </div>
      {report.error && <p className="mt-1.5 text-xs leading-relaxed text-ink-2">{report.error}</p>}
    </div>
  )
}

function ClaimRow({ claim, open, onToggle, onFlag, flagging, passages }: {
  claim: ClaimWithSources
  open: boolean
  onToggle: () => void
  onFlag: () => void
  flagging: boolean
  passages: Record<string, string[]>
}) {
  return (
    <li id={`claim-${claim.id}`} className={cx('border-b border-line last:border-0', open && 'bg-paper/50')}>
      <button onClick={onToggle} aria-expanded={open} className="flex w-full items-start gap-3 px-5 py-3 text-left">
        <span className="mt-0.5 font-mono text-xs font-semibold text-accent-2">{claim.id}</span>
        <span className="min-w-0 flex-1 text-sm text-ink">{claim.text}</span>
        <span className="flex shrink-0 flex-wrap items-center justify-end gap-1.5">
          {claim.needs_research && <Badge tone="warn"><Flag className="size-3" /> needs research</Badge>}
          <EvidenceBadge status={claim.qc_status ?? claim.status} />
          <ChevronDown className={cx('size-4 text-muted transition-transform', open && 'rotate-180')} aria-hidden />
        </span>
      </button>
      {open && (
        <div className="space-y-3 px-5 pb-4 pl-14 text-[13px]">
          <dl className="grid gap-2 sm:grid-cols-2">
            <div><dt className="text-xs text-muted">Lesson section</dt><dd className="font-mono text-ink-2">{claim.section_id}</dd></div>
            <div>
              <dt className="text-xs text-muted">Automated quote check</dt>
              <dd className="flex items-center gap-2"><EvidenceBadge status={claim.status} /></dd>
            </div>
            {claim.qc_status && (
              <div className="sm:col-span-2">
                <dt className="text-xs text-muted">QC Layer 1 review (final status)</dt>
                <dd className="text-ink-2"><EvidenceBadge status={claim.qc_status} /> {claim.qc_rationale}</dd>
              </div>
            )}
          </dl>
          {claim.verification_note && <p className="text-ink-2">{claim.verification_note}</p>}
          {claim.evidence_excerpt ? (
            <blockquote className="border-l-2 border-accent pl-3 italic text-ink-2">“{claim.evidence_excerpt}”</blockquote>
          ) : (
            <p className="text-muted">No evidence excerpt.</p>
          )}
          <div>
            <p className="mb-1 text-xs text-muted">Cited sources</p>
            {claim.sources.length === 0 ? (
              <p className="text-bad">None. This claim is not backed by any retrieved source.</p>
            ) : (
              <ul className="space-y-2">
                {claim.sources.map((s) => (
                  <li key={s.source_id} className="rounded-md border border-line bg-card p-2.5">
                    <span className="font-mono text-xs font-semibold text-accent-2">{s.source_id}</span>{' '}
                    {s.url ? <a href={s.url} target="_blank" rel="noreferrer noopener" className="text-ink hover:underline">{s.title}</a> : s.title}{' '}
                    <span className="text-xs text-muted">· {s.reliability_tier} · {s.evidence_use.replace('_', ' ')}</span>
                    {passages[s.source_id]?.length ? (
                      <details className="mt-1.5">
                        <summary className="cursor-pointer text-xs text-accent">Show retrieved passages ({passages[s.source_id].length})</summary>
                        <ul className="mt-1.5 space-y-1.5">
                          {passages[s.source_id].map((p, i) => <li key={i} className="rounded bg-paper-2 p-2 text-xs text-ink-2">{p}</li>)}
                        </ul>
                      </details>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <Button size="sm" variant={claim.needs_research ? 'secondary' : 'ghost'} onClick={onFlag} loading={flagging} icon={<Flag className="size-3.5" />}>
            {claim.needs_research ? 'Clear "needs research" flag' : 'Flag as needing more research'}
          </Button>
        </div>
      )}
    </li>
  )
}

export default function ResearchTab({ lesson, setLesson, focus }: WorkspaceProps) {
  const sources = useAsync(() => api.sources(lesson.id), [lesson.id, lesson.source_count])
  const claims = useAsync(() => api.claims(lesson.id), [lesson.id, lesson.current_version?.id, lesson.current_version?.updated_at, lesson.latest_reports.factual?.id])
  const [typeFilter, setTypeFilter] = useState<SourceType | 'all'>('all')
  const [statusFilter, setStatusFilter] = useState<(typeof STATUS_FILTERS)[number]>('all')
  const [openClaim, setOpenClaim] = useState<string | null>(focus ?? null)
  const [busy, setBusy] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [lastRun, setLastRun] = useState<ResearchResult | null>(null)

  const researchStep = lesson.workflow.find((s) => s.name === 'research')
  const providerReports = (lastRun ?? (researchStep?.summary as ResearchResult | null))?.providers ?? []
  const passages = useMemo(
    () => Object.fromEntries((sources.data?.sources ?? []).map((s) => [s.source_id, s.passages])),
    [sources.data],
  )

  useEffect(() => {
    if (focus) {
      setOpenClaim(focus)
      setTimeout(() => document.getElementById(`claim-${focus}`)?.scrollIntoView({ block: 'center' }), 100)
    }
  }, [focus, claims.data])

  const retryProvider = async (provider: string) => {
    setBusy(provider)
    setActionError(null)
    try {
      const r = await api.research(lesson.id, [provider])
      setLastRun(r.research)
      setLesson(r.lesson)
    } catch (e) {
      setActionError(errorMessage(e))
    } finally {
      setBusy(null)
    }
  }

  const flag = async (c: ClaimWithSources) => {
    setBusy(c.id)
    try {
      setLesson(await api.flagClaim(lesson.id, c.id, !c.needs_research))
    } catch (e) {
      setActionError(errorMessage(e))
    } finally {
      setBusy(null)
    }
  }

  const visibleSources = (sources.data?.sources ?? []).filter((s) => typeFilter === 'all' || s.source_type === typeFilter)
  const allClaims = claims.data?.claims ?? []
  const visibleClaims = allClaims.filter((c) =>
    statusFilter === 'all' ? true : statusFilter === 'flagged' ? c.needs_research : (c.qc_status ?? c.status) === statusFilter,
  )
  const counts = allClaims.reduce<Record<string, number>>((acc, c) => {
    const s = c.qc_status ?? c.status ?? 'none'
    acc[s] = (acc[s] ?? 0) + 1
    return acc
  }, {})

  return (
    <div className="space-y-6">
      {actionError && <Alert tone="bad">{actionError}</Alert>}
      {providerReports.length > 0 && (
        <div className="grid grid-cols-1 gap-2 lg:grid-cols-3">
          {providerReports.map((p) => <ProviderStatus key={p.provider} report={p} busy={busy === p.provider} onRetry={() => void retryProvider(p.provider)} />)}
        </div>
      )}

      <Card>
        <CardHeader
          title="Evidence traceability"
          description={
            claims.data?.qc_review
              ? `Statuses combine the automated quote check with QC Layer 1 (report on v${claims.data.qc_review.version_number}${claims.data.qc_review.stale ? ', stale' : ''}).`
              : 'Statuses come from the automated quote check. Run QC Layer 1 for an independent review.'
          }
        />
        {claims.loading && !claims.data ? (
          <Spinner />
        ) : allClaims.length === 0 ? (
          <EmptyState title="No claims yet">Claims appear after the lesson is generated. Each one links to the evidence behind it.</EmptyState>
        ) : (
          <>
            <div className="flex flex-wrap gap-1.5 border-b border-line px-5 py-3" role="group" aria-label="Filter claims">
              {STATUS_FILTERS.map((f) => {
                const n = f === 'all' ? allClaims.length : f === 'flagged' ? allClaims.filter((c) => c.needs_research).length : counts[f] ?? 0
                if (n === 0 && f !== 'all') return null
                return (
                  <button key={f} onClick={() => setStatusFilter(f)} aria-pressed={statusFilter === f}
                    className={cx('rounded-full border px-2.5 py-1 text-xs', statusFilter === f ? 'border-ink bg-ink text-paper' : 'border-line text-ink-2 hover:bg-paper-2')}>
                    {f === 'all' ? 'All' : f === 'flagged' ? 'Needs research' : f} · {n}
                  </button>
                )
              })}
            </div>
            <ul>
              {visibleClaims.map((c) => (
                <ClaimRow key={c.id} claim={c} open={openClaim === c.id} onToggle={() => setOpenClaim(openClaim === c.id ? null : c.id)}
                  onFlag={() => void flag(c)} flagging={busy === c.id} passages={passages} />
              ))}
            </ul>
          </>
        )}
      </Card>

      <Card>
        <CardHeader
          title="Sources"
          description="A URL alone is never treated as proof. Books and videos are metadata only and cannot support a claim."
          action={
            <div className="flex rounded-lg border border-line p-0.5 text-xs" role="group" aria-label="Filter sources">
              {(['all', 'website', 'book', 'youtube'] as const).map((t) => (
                <button key={t} onClick={() => setTypeFilter(t)} aria-pressed={typeFilter === t}
                  className={cx('rounded-md px-2.5 py-1', typeFilter === t ? 'bg-ink text-paper' : 'text-ink-2 hover:bg-paper-2')}>
                  {t === 'all' ? `All (${sources.data?.sources.length ?? 0})` : t === 'youtube' ? `Videos (${lesson.source_counts.youtube})` : `${t[0].toUpperCase()}${t.slice(1)}s (${lesson.source_counts[t]})`}
                </button>
              ))}
            </div>
          }
        />
        <div className="space-y-3 p-5">
          {sources.loading && !sources.data ? <Spinner /> : visibleSources.length === 0 ? (
            <EmptyState title="No sources">{researchStep?.status === 'Pending' ? 'Run research from the Overview tab.' : 'No sources of this type were found.'}</EmptyState>
          ) : visibleSources.map((s) => <SourceCard key={s.id} source={s} />)}
        </div>
      </Card>
    </div>
  )
}
