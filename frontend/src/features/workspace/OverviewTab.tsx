import { Play, RotateCw, Square } from 'lucide-react'
import { StepIcon } from '../../components/StatusBadges'
import { Alert, Badge, Button, Card, CardHeader, cx } from '../../components/ui'
import type { WorkspaceProps } from '../../pages/LessonWorkspace'
import type { StepStatus, TimingReport, WorkflowStep } from '../../types/api'
import { formatDateTime, humanize } from '../../utils/format'
import { STAGE_STEPS, STEP_TO_STAGE, type StageKey } from './usePipeline'

const MANUAL_STEPS = new Set(['instructor_review', 'finalization', 'export'])

function summaryText(step: WorkflowStep): string | null {
  const s = step.summary as Record<string, unknown> | null
  if (!s) return null
  switch (step.name) {
    case 'objective_analysis':
      return `${s.outcomes} learning outcomes, ${s.concepts} key concepts`
    case 'research':
      return `${s.total_sources} sources (${s.evidence_sources} usable as evidence), ${s.duplicates_removed} duplicates removed`
    case 'source_evaluation':
      return `${s.evidence} evidence · ${s.supplementary} supplementary · ${s.further_reading} further reading · ${s.excluded} excluded`
    case 'evidence_extraction':
      return `${s.passages} passages from ${s.evidence_sources} sources`
    case 'lesson_generation':
      return `${s.sections} sections, ${s.claims} mapped claims, ${s.questions} questions`
    case 'timing_validation':
      return `${s.total_minutes} minutes${s.revision_rounds ? `, after ${s.revision_rounds} shortening round(s)` : ''}`
    case 'qc_factual':
    case 'qc_instructional':
      return `Score ${s.score}/100 for version ${s.version_number}, ${s.issues} issues`
    case 'instructor_review':
      return s.pending_recommendations != null ? `${s.pending_recommendations} recommendations pending` : 'Edits saved'
    case 'finalization':
      return `Version ${s.version_number} finalized`
    case 'export':
      return `${humanize(String(s.format))} of version ${s.version_number}`
  }
  return null
}

export function TimingBar({ timing }: { timing: TimingReport }) {
  const palette = ['#0f766e', '#2b8f86', '#5aa8a0', '#3b5b9a', '#6b85b8', '#a2630b', '#c48a3a', '#6b7384', '#9aa1ae', '#1b2638', '#4a5568', '#7c8796']
  const width = Math.max(timing.total_minutes, timing.limit_minutes)
  return (
    <div>
      <div className="flex h-3 overflow-hidden rounded-full bg-paper-2" role="img" aria-label={`Time allocation: ${timing.total_minutes} of ${timing.limit_minutes} minutes`}>
        {timing.sections.map((s, i) => (
          <div key={s.id} title={`${s.title}: ${s.duration_minutes} min`} style={{ width: `${(s.duration_minutes / width) * 100}%`, background: palette[i % palette.length] }} className="border-r border-card last:border-0" />
        ))}
      </div>
      <ul className="mt-3 grid gap-x-6 gap-y-1 text-[13px] sm:grid-cols-2">
        {timing.sections.map((s, i) => (
          <li key={s.id} className="flex items-center gap-2">
            <span className="size-2.5 shrink-0 rounded-sm" style={{ background: palette[i % palette.length] }} aria-hidden />
            <span className="min-w-0 flex-1 truncate text-ink-2">{s.title}</span>
            <span className="tabular-nums text-muted">{s.duration_minutes} min</span>
          </li>
        ))}
      </ul>
      <p className="mt-3 border-t border-line pt-2 text-[13px] text-ink-2">
        Sum of sections: <strong className="tabular-nums">{timing.total_minutes} min</strong> of {timing.limit_minutes} allowed.{' '}
        {Object.entries(timing.by_category).map(([k, v]) => `${k} ${v}`).join(' · ')}
      </p>
    </div>
  )
}

export default function OverviewTab({ lesson, pipeline }: WorkspaceProps) {
  const runningSteps = new Set(pipeline.running ? STAGE_STEPS[pipeline.running] : [])
  const statusOf = (step: WorkflowStep): StepStatus => (runningSteps.has(step.name) ? (step.status === 'Failed' ? 'Retrying' : 'Running') : step.status)
  const a = lesson.objective_analysis
  const firstIncomplete = (['analysis', 'research', 'generate', 'qc_factual', 'qc_instructional'] as StageKey[]).find((stage) =>
    STAGE_STEPS[stage].some((n) => lesson.workflow.find((w) => w.name === n)?.status !== 'Completed'),
  )

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.1fr_1fr]">
      <Card>
        <CardHeader
          title="Workflow"
          description="Statuses come from completed backend operations."
          action={
            pipeline.running ? (
              <Button size="sm" variant="secondary" onClick={pipeline.stop} icon={<Square className="size-3.5" />}>Stop after this step</Button>
            ) : firstIncomplete ? (
              <Button size="sm" variant="primary" onClick={() => void pipeline.runFrom(firstIncomplete)} icon={<Play className="size-3.5" />}>
                {firstIncomplete === 'analysis' ? 'Run full workflow' : 'Continue workflow'}
              </Button>
            ) : null
          }
        />
        {pipeline.error && (
          <div className="px-5 pt-4">
            <Alert tone="bad" title={`${humanize(pipeline.error.stage)} did not complete`}>{pipeline.error.message}</Alert>
          </div>
        )}
        <ol className="px-5 py-3">
          {lesson.workflow.map((step, i) => {
            const status = statusOf(step)
            const stage = STEP_TO_STAGE[step.name]
            const isFirstOfStage = stage && STAGE_STEPS[stage][0] === step.name
            return (
              <li key={step.name} className="relative flex gap-3 pb-4 last:pb-0">
                {i < lesson.workflow.length - 1 && <span className="absolute left-[7px] top-6 h-[calc(100%-18px)] w-px bg-line" aria-hidden />}
                <div className="pt-0.5"><StepIcon status={status} /></div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={cx('text-sm', status === 'Pending' ? 'text-muted' : 'font-medium text-ink')}>{step.label}</span>
                    <span className="text-xs text-muted">{status}</span>
                    {step.retry_count > 0 && <Badge>retried {step.retry_count}×</Badge>}
                    {MANUAL_STEPS.has(step.name) && status === 'Pending' && <span className="text-xs text-muted">· done by you</span>}
                  </div>
                  {summaryText(step) && status === 'Completed' && <p className="mt-0.5 text-[13px] text-ink-2">{summaryText(step)}</p>}
                  {step.error_message && (
                    <p className={cx('mt-1 whitespace-pre-line text-[13px]', step.status === 'Failed' ? 'text-bad' : 'text-warn')}>{step.error_message}</p>
                  )}
                  {step.completed_at && <p className="mt-0.5 text-xs text-muted">{formatDateTime(step.completed_at)}</p>}
                  {stage && isFirstOfStage && step.status === 'Failed' && !pipeline.running && (
                    <Button size="sm" className="mt-2" onClick={() => void pipeline.runStage(stage)} icon={<RotateCw className="size-3.5" />}>
                      Retry this step
                    </Button>
                  )}
                  {stage === 'research' && step.name === 'research' && step.status === 'Failed' && !pipeline.running && (
                    <Button size="sm" variant="ghost" className="ml-2 mt-2" onClick={() => void pipeline.runFrom('generate')}>
                      Continue without web evidence
                    </Button>
                  )}
                </div>
              </li>
            )
          })}
        </ol>
      </Card>

      <div className="space-y-6">
        <Card>
          <CardHeader title="Learning objective" description="Your original wording is kept separately from the AI's interpretation." />
          <div className="space-y-4 px-5 py-4 text-sm">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-muted">Original (instructor)</p>
              <p className="mt-1 text-ink">{a?.original_objective ?? lesson.learning_objective}</p>
            </div>
            {a ? (
              <>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-muted">AI interpretation</p>
                  <p className="mt-1 text-ink-2">{a.interpretation}</p>
                </div>
                <div>
                  <p className="text-xs font-medium uppercase tracking-wide text-muted">Measurable outcomes</p>
                  <ul className="mt-1 space-y-1">
                    {a.learning_outcomes.map((o) => (
                      <li key={o.id} className="flex gap-2 text-ink-2">
                        <span className="font-mono text-xs font-semibold text-accent-2">{o.id}</span>
                        <span className="flex-1">{o.outcome} <span className="text-xs text-muted">({o.bloom_level}; {o.measurable_by})</span></span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {a.key_concepts.map((c) => <Badge key={c} tone="accent">{c}</Badge>)}
                </div>
                <dl className="grid gap-3 text-[13px] sm:grid-cols-2">
                  <div><dt className="font-medium text-ink">Prerequisites</dt><dd className="text-ink-2">{a.prerequisites.join('; ') || 'None'}</dd></div>
                  <div><dt className="font-medium text-ink">Assessment</dt><dd className="text-ink-2">{a.assessment_methods.join('; ')}</dd></div>
                  <div className="sm:col-span-2"><dt className="font-medium text-ink">Expected difficulty</dt><dd className="text-ink-2">{a.expected_difficulty}</dd></div>
                </dl>
              </>
            ) : (
              <p className="text-muted">The objective has not been analysed yet.</p>
            )}
          </div>
        </Card>
        {lesson.timing && (
          <Card>
            <CardHeader
              title="45-minute plan"
              description="Computed by the backend from section durations."
              action={<Badge tone={lesson.timing.compliant ? 'ok' : 'bad'}>{lesson.timing.compliant ? 'Within limit' : 'Over limit'}</Badge>}
            />
            <div className="px-5 py-4">
              {!lesson.timing.compliant && (
                <div className="mb-3"><Alert tone="bad">{lesson.timing.issues.join(' ')}</Alert></div>
              )}
              <TimingBar timing={lesson.timing} />
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}
