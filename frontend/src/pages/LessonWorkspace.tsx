import { ArrowLeft, Clock } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { LessonStatusBadge, ScoreBadge } from '../components/StatusBadges'
import { Alert, Badge, ConfirmDialog, Spinner, Tabs } from '../components/ui'
import ContentTab from '../features/workspace/ContentTab'
import ExportTab from '../features/workspace/ExportTab'
import OverviewTab from '../features/workspace/OverviewTab'
import PreviewTab from '../features/workspace/PreviewTab'
import QualityTab from '../features/workspace/QualityTab'
import ResearchTab from '../features/workspace/ResearchTab'
import { usePipeline } from '../features/workspace/usePipeline'
import { useAsync } from '../hooks/useAsync'
import { api } from '../services/api'
import type { LessonDetail } from '../types/api'

type TabId = 'overview' | 'research' | 'content' | 'quality' | 'preview' | 'export'

export interface WorkspaceProps {
  lesson: LessonDetail
  setLesson: (l: LessonDetail) => void
  refresh: () => Promise<unknown>
  pipeline: ReturnType<typeof usePipeline>
  goTo: (tab: TabId, focus?: string) => void
  focus?: string
}

export default function LessonWorkspace() {
  const id = Number(useParams().id)
  const [params, setParams] = useSearchParams()
  const [tab, setTab] = useState<TabId>((params.get('tab') as TabId) || 'overview')
  const [focus, setFocus] = useState<string | undefined>()
  const { data: lesson, setData, error, loading, reload } = useAsync(() => api.getLesson(id), [id])
  const setLesson = useCallback((l: LessonDetail) => setData(l), [setData])
  const pipeline = usePipeline(id, setLesson)
  const autoRan = useRef(false)

  // Coming from "Generate lesson": run the full workflow once.
  useEffect(() => {
    if (lesson && params.get('run') === '1' && !autoRan.current) {
      autoRan.current = true
      params.delete('run')
      setParams(params, { replace: true })
      void pipeline.runFrom('analysis')
    }
  }, [lesson, params, setParams, pipeline])

  const goTo = (t: TabId, f?: string) => {
    setTab(t)
    setFocus(f)
    window.scrollTo({ top: 0 })
  }

  if (loading && !lesson) return <Spinner label="Loading lesson" />
  if (error || !lesson)
    return (
      <Alert tone="bad" title="Lesson unavailable">
        {error?.message ?? 'Not found.'} <Link to="/lessons" className="underline">Back to my lessons</Link>
      </Alert>
    )

  const staleCount = [lesson.latest_reports.factual, lesson.latest_reports.instructional].filter((r) => r?.stale).length
  const props: WorkspaceProps = { lesson, setLesson, refresh: reload, pipeline, goTo, focus }

  return (
    <div>
      <Link to="/lessons" className="mb-3 inline-flex items-center gap-1 text-sm text-muted hover:text-ink">
        <ArrowLeft className="size-3.5" /> My lessons
      </Link>
      <header className="mb-5">
        <div className="flex flex-wrap items-center gap-2">
          <LessonStatusBadge status={lesson.status} />
          {lesson.current_version && <Badge>Version {lesson.current_version.version_number}</Badge>}
          {lesson.timing && (
            <Badge tone={lesson.timing.compliant ? 'neutral' : 'bad'}>
              <Clock className="size-3" aria-hidden /> {lesson.timing.total_minutes} / {lesson.timing.limit_minutes} min
            </Badge>
          )}
          {lesson.is_demo && <Badge tone="warn" title="Produced from labelled offline fixtures, not live research or a live model">Offline demo</Badge>}
        </div>
        <h1 className="mt-2 font-serif text-[28px] leading-tight text-ink">{lesson.title}</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">{lesson.learning_objective}</p>
        <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted">
          <span className="flex items-center gap-1.5">Factual QC <ScoreBadge score={lesson.latest_reports.factual?.score} stale={lesson.latest_reports.factual?.stale} /></span>
          <span className="flex items-center gap-1.5">Instructional QC <ScoreBadge score={lesson.latest_reports.instructional?.score} stale={lesson.latest_reports.instructional?.stale} /></span>
        </div>
      </header>

      <Tabs<TabId>
        label="Lesson workspace"
        value={tab}
        onChange={(t) => goTo(t)}
        tabs={[
          { id: 'overview', label: 'Overview' },
          { id: 'research', label: 'Research', badge: lesson.source_count ? <Badge>{lesson.source_count}</Badge> : undefined },
          { id: 'content', label: 'Lesson Content' },
          { id: 'quality', label: 'Quality Control', badge: staleCount ? <Badge tone="warn">stale</Badge> : undefined },
          { id: 'preview', label: 'Final Preview' },
          { id: 'export', label: 'Export' },
        ]}
      />
      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} className="pt-6">
        {tab === 'overview' && <OverviewTab {...props} />}
        {tab === 'research' && <ResearchTab {...props} />}
        {tab === 'content' && <ContentTab {...props} />}
        {tab === 'quality' && <QualityTab {...props} />}
        {tab === 'preview' && <PreviewTab {...props} />}
        {tab === 'export' && <ExportTab {...props} />}
      </div>

      <ConfirmDialog
        open={pipeline.needsOverwriteConfirm}
        title="Replace edited content?"
        confirmLabel="Regenerate as new version"
        onCancel={() => pipeline.setNeedsOverwriteConfirm(false)}
        onConfirm={() => {
          pipeline.setNeedsOverwriteConfirm(false)
          void pipeline.runFrom('generate', { confirmOverwrite: true })
        }}
      >
        This lesson contains your edits. Regenerating writes a new AI version and makes it current. Your edited version stays in
        version history and can be restored from the Export tab.
      </ConfirmDialog>
    </div>
  )
}
