import { CheckCircle2, CircleDashed, Clock, Loader2, RotateCw, XCircle } from 'lucide-react'
import type { EvidenceStatus, LessonStatus, Severity, StepStatus } from '../types/api'
import { evidenceTone, scoreTone, severityTone, type Tone } from '../utils/format'
import { Badge } from './ui'

const lessonTone: Record<LessonStatus, Tone> = {
  Draft: 'neutral',
  Researching: 'info',
  Generated: 'accent',
  'QC Reviewed': 'ok',
  Finalized: 'ok',
}

export function LessonStatusBadge({ status }: { status: LessonStatus }) {
  return <Badge tone={lessonTone[status]}>{status === 'Finalized' && <CheckCircle2 className="size-3" aria-hidden />}{status}</Badge>
}

export function EvidenceBadge({ status }: { status: EvidenceStatus | null }) {
  if (!status) return <Badge>Not checked</Badge>
  return <Badge tone={evidenceTone[status]}>{status}</Badge>
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <Badge tone={severityTone[severity]}>{severity}</Badge>
}

export function ScoreBadge({ score, stale }: { score: number | null | undefined; stale?: boolean }) {
  if (score == null) return <Badge>Not run</Badge>
  return (
    <Badge tone={stale ? 'warn' : scoreTone(score)} title={stale ? 'Stale: lesson changed since this check' : undefined}>
      {score}/100{stale && ' · stale'}
    </Badge>
  )
}

const stepIcon: Record<StepStatus, { Icon: typeof Clock; cls: string }> = {
  Pending: { Icon: CircleDashed, cls: 'text-muted' },
  Running: { Icon: Loader2, cls: 'text-accent animate-spin' },
  Retrying: { Icon: RotateCw, cls: 'text-warn animate-spin' },
  Completed: { Icon: CheckCircle2, cls: 'text-ok' },
  Failed: { Icon: XCircle, cls: 'text-bad' },
}

export function StepIcon({ status }: { status: StepStatus }) {
  const { Icon, cls } = stepIcon[status]
  return <Icon className={`size-4 shrink-0 ${cls}`} aria-label={status} />
}
