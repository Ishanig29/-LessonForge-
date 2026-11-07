import { ArrowRight, BookOpen, FilePlus2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { LessonStatusBadge, ScoreBadge } from '../components/StatusBadges'
import { Alert, Badge, Button, Card, CardHeader, EmptyState, PageHeader, Spinner, Stat } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { api } from '../services/api'
import type { LessonStatus } from '../types/api'
import { relativeTime } from '../utils/format'

const STATUSES: LessonStatus[] = ['Draft', 'Researching', 'Generated', 'QC Reviewed', 'Finalized']

export default function Dashboard() {
  const lessons = useAsync(() => api.listLessons(), [])
  const stats = useAsync(() => api.stats(), [])
  const recent = lessons.data?.lessons.slice(0, 6) ?? []

  return (
    <>
      <PageHeader
        title="Welcome back"
        subtitle="Turn a learning objective into a researched, verified lesson of 45 minutes or less."
        action={
          <Link to="/create">
            <Button variant="primary" icon={<FilePlus2 className="size-4" />}>Create new lesson</Button>
          </Link>
        }
      />

      {(lessons.error || stats.error) && (
        <div className="mb-6">
          <Alert tone="bad" title="Could not load your lessons">{(lessons.error ?? stats.error)?.message}</Alert>
        </div>
      )}

      {stats.data && stats.data.lessons_total > 0 && (
        <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Stat label="Lessons" value={stats.data.lessons_total} />
          {STATUSES.map((s) => (
            <Stat key={s} label={s} value={stats.data!.lessons_by_status[s] ?? 0} />
          ))}
        </div>
      )}

      <Card>
        <CardHeader
          title="Recent lessons"
          description="Most recently updated first"
          action={recent.length > 0 && <Link to="/lessons" className="text-sm text-accent hover:underline">View all</Link>}
        />
        {lessons.loading && !lessons.data ? (
          <Spinner />
        ) : recent.length === 0 ? (
          <EmptyState
            icon={<BookOpen className="size-5" />}
            title="No lessons yet"
            action={<Link to="/create"><Button variant="primary">Create your first lesson</Button></Link>}
          >
            Start with a title and a learning objective. LessonForge analyses the objective, researches sources,
            writes the lesson and checks it twice.
          </EmptyState>
        ) : (
          <ul className="divide-y divide-line">
            {recent.map((l) => (
              <li key={l.id}>
                <Link to={`/lessons/${l.id}`} className="group flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-4 hover:bg-paper/60">
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium text-ink group-hover:text-accent-2">{l.title}</p>
                    <p className="mt-0.5 truncate text-[13px] text-muted">{l.learning_objective}</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {l.is_demo && <Badge tone="warn">Demo</Badge>}
                    <LessonStatusBadge status={l.status} />
                    {l.duration_minutes != null && <Badge>{l.duration_minutes} min</Badge>}
                    {l.qc.factual && <ScoreBadge score={l.qc.factual.score} stale={l.qc.factual.stale} />}
                    <span className="w-20 text-right text-xs text-muted">{relativeTime(l.updated_at)}</span>
                    <ArrowRight className="size-4 text-muted" aria-hidden />
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  )
}
