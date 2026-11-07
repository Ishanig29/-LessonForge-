import { Copy, FilePlus2, Search, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { LessonStatusBadge, ScoreBadge } from '../components/StatusBadges'
import { Alert, Badge, Button, Card, ConfirmDialog, EmptyState, PageHeader, Spinner, TextInput } from '../components/ui'
import { errorMessage, useAsync } from '../hooks/useAsync'
import { api } from '../services/api'
import type { LessonSummary } from '../types/api'
import { formatDate } from '../utils/format'

export default function MyLessons() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [debounced, setDebounced] = useState('')
  const [toDelete, setToDelete] = useState<LessonSummary | null>(null)
  const [busy, setBusy] = useState<number | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(query.trim()), 250)
    return () => clearTimeout(t)
  }, [query])
  const { data, loading, error, reload } = useAsync(() => api.listLessons(debounced), [debounced])

  const duplicate = async (l: LessonSummary) => {
    setBusy(l.id)
    try {
      const copy = await api.duplicateLesson(l.id)
      navigate(`/lessons/${copy.id}`)
    } catch (e) {
      setActionError(errorMessage(e))
    } finally {
      setBusy(null)
    }
  }

  const remove = async () => {
    if (!toDelete) return
    setBusy(toDelete.id)
    try {
      await api.deleteLesson(toDelete.id)
      setToDelete(null)
      await reload()
    } catch (e) {
      setActionError(errorMessage(e))
    } finally {
      setBusy(null)
    }
  }

  return (
    <>
      <PageHeader
        title="My lessons"
        subtitle="Open, duplicate or delete saved lessons."
        action={<Link to="/create"><Button variant="primary" icon={<FilePlus2 className="size-4" />}>New lesson</Button></Link>}
      />
      <div className="relative mb-4 max-w-md">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
        <TextInput aria-label="Search lessons" placeholder="Search by title or objective" value={query} onChange={(e) => setQuery(e.target.value)} className="pl-9" />
      </div>
      {(error || actionError) && <div className="mb-4"><Alert tone="bad">{error?.message ?? actionError}</Alert></div>}
      <Card>
        {loading && !data ? (
          <Spinner />
        ) : !data?.lessons.length ? (
          <EmptyState title={debounced ? 'No lessons match your search' : 'No saved lessons'}>
            {debounced ? 'Try a different word.' : 'Lessons you create are saved automatically and appear here.'}
          </EmptyState>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-line text-left text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th className="px-5 py-3 font-medium">Lesson</th>
                  <th className="px-3 py-3 font-medium">Status</th>
                  <th className="px-3 py-3 font-medium">Version</th>
                  <th className="px-3 py-3 font-medium">Factual QC</th>
                  <th className="px-3 py-3 font-medium">Instructional QC</th>
                  <th className="px-3 py-3 font-medium">Updated</th>
                  <th className="px-5 py-3"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {data.lessons.map((l) => (
                  <tr key={l.id} className="hover:bg-paper/60">
                    <td className="max-w-sm px-5 py-3">
                      <Link to={`/lessons/${l.id}`} className="font-medium text-ink hover:text-accent-2">{l.title}</Link>
                      <div className="mt-0.5 flex gap-1.5 text-xs text-muted">
                        {l.is_demo && <Badge tone="warn">Demo</Badge>}
                        <span>{l.difficulty} · {l.delivery_mode}</span>
                      </div>
                    </td>
                    <td className="px-3 py-3"><LessonStatusBadge status={l.status} /></td>
                    <td className="px-3 py-3 tabular-nums text-ink-2">{l.current_version_number ? `v${l.current_version_number} · ${l.duration_minutes} min` : '—'}</td>
                    <td className="px-3 py-3"><ScoreBadge score={l.qc.factual?.score} stale={l.qc.factual?.stale} /></td>
                    <td className="px-3 py-3"><ScoreBadge score={l.qc.instructional?.score} stale={l.qc.instructional?.stale} /></td>
                    <td className="px-3 py-3 text-ink-2">{formatDate(l.updated_at)}</td>
                    <td className="px-5 py-3">
                      <div className="flex justify-end gap-1">
                        <Button size="sm" variant="ghost" onClick={() => duplicate(l)} loading={busy === l.id && !toDelete} aria-label={`Duplicate ${l.title}`} icon={<Copy className="size-3.5" />} />
                        <Button size="sm" variant="ghost" onClick={() => setToDelete(l)} aria-label={`Delete ${l.title}`} icon={<Trash2 className="size-3.5 text-bad" />} />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <ConfirmDialog
        open={!!toDelete}
        title="Delete lesson?"
        danger
        confirmLabel="Delete permanently"
        loading={busy === toDelete?.id}
        onCancel={() => setToDelete(null)}
        onConfirm={remove}
      >
        <strong className="text-ink">{toDelete?.title}</strong> and all of its versions, research sources and QC reports will be
        permanently deleted. This cannot be undone.
      </ConfirmDialog>
    </>
  )
}
