import { BookOpen, ExternalLink, Globe, PlayCircle } from 'lucide-react'
import type { ReactNode } from 'react'
import type { EvidenceUse, ResearchSource } from '../types/api'
import { formatDate, type Tone } from '../utils/format'
import { Badge } from './ui'

export const evidenceUseLabel: Record<EvidenceUse, { label: string; tone: Tone; help: string }> = {
  evidence: { label: 'Evidence', tone: 'ok', help: 'Retrieved page text is available and used to verify claims.' },
  supplementary: { label: 'Supplementary', tone: 'info', help: 'Not used as evidence (no retrieved text, or low relevance).' },
  further_reading: { label: 'Further reading', tone: 'neutral', help: 'Book metadata only. The book was not read.' },
  excluded: { label: 'Excluded', tone: 'bad', help: 'Judged irrelevant to the lesson topic.' },
}

/** Strip markdown punctuation so retrieved snippets read as plain text. */
const plain = (t: string) => t.replace(/[`*_#>]+/g, '').replace(/\[!NOTE\]/g, '').replace(/\s+/g, ' ').trim()

const typeIcon = { website: Globe, book: BookOpen, youtube: PlayCircle }

export function SourceCard({ source, extra, compact }: { source: ResearchSource; extra?: ReactNode; compact?: boolean }) {
  const Icon = typeIcon[source.source_type]
  const use = evidenceUseLabel[source.evidence_use]
  const thumb = source.metadata.thumbnail as string | undefined
  const duration = source.metadata.duration_seconds as number | undefined
  return (
    <article className="flex gap-3 rounded-lg border border-line bg-card p-4">
      {thumb ? (
        <img src={thumb} alt="" className="h-16 w-28 shrink-0 rounded object-cover" loading="lazy" />
      ) : (
        <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-paper-2 text-ink-2"><Icon className="size-4" aria-hidden /></div>
      )}
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="font-mono text-xs font-semibold text-accent-2">{source.source_id}</span>
          <Badge tone={use.tone} title={use.help}>{use.label}</Badge>
          <Badge>{source.reliability_tier}</Badge>
          {source.is_demo && <Badge tone="warn" title={String(source.metadata.capture_note ?? '')}>Demo fixture</Badge>}
        </div>
        <h3 className="mt-1 text-sm font-medium leading-snug text-ink">
          {source.url ? (
            <a href={source.url} target="_blank" rel="noreferrer noopener" className="hover:text-accent-2 hover:underline">
              {source.title} <ExternalLink className="inline size-3 align-baseline text-muted" aria-label="(opens in new tab)" />
            </a>
          ) : (
            source.title
          )}
        </h3>
        <p className="mt-0.5 text-xs text-muted">
          {source.author_or_domain ?? 'Unknown'}
          {source.published_date && ` · published ${String(source.published_date).slice(0, 10)}`}
          {duration ? ` · ${Math.round(duration / 60)} min` : ''}
          {` · retrieved ${formatDate(source.retrieved_at)}`}
        </p>
        {!compact && source.description && <p className="mt-2 line-clamp-2 text-[13px] text-ink-2">{plain(source.description)}</p>}
        {!compact && source.reliability_rationale && (
          <p className="mt-2 text-xs text-muted"><span className="font-medium text-ink-2">Why this rating:</span> {source.reliability_rationale}</p>
        )}
        {extra}
      </div>
    </article>
  )
}
