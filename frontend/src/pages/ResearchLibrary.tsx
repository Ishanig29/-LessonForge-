import { Library, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { SourceCard } from '../components/SourceCard'
import { Alert, Card, EmptyState, PageHeader, Select, Spinner, TextInput, cx } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { api } from '../services/api'

const TYPES = [
  { id: '', label: 'All' },
  { id: 'website', label: 'Websites' },
  { id: 'book', label: 'Books' },
  { id: 'youtube', label: 'Videos' },
]

export default function ResearchLibrary() {
  const [type, setType] = useState('')
  const [use, setUse] = useState('')
  const [q, setQ] = useState('')
  const [debounced, setDebounced] = useState('')
  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 250)
    return () => clearTimeout(t)
  }, [q])
  const { data, loading, error } = useAsync(() => api.library({ type, q: debounced, evidence_use: use }), [type, debounced, use])

  return (
    <>
      <PageHeader title="Research library" subtitle="Every source LessonForge has collected, across all lessons." />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div role="group" aria-label="Filter by source type" className="flex rounded-lg border border-line bg-card p-0.5">
          {TYPES.map((t) => (
            <button
              key={t.id}
              onClick={() => setType(t.id)}
              aria-pressed={type === t.id}
              className={cx('rounded-md px-3 py-1.5 text-sm', type === t.id ? 'bg-ink text-paper' : 'text-ink-2 hover:bg-paper-2')}
            >
              {t.label}
            </button>
          ))}
        </div>
        <Select aria-label="Filter by evidence use" value={use} onChange={(e) => setUse(e.target.value)} className="w-48">
          <option value="">Any evidence use</option>
          <option value="evidence">Used as evidence</option>
          <option value="supplementary">Supplementary</option>
          <option value="further_reading">Further reading</option>
          <option value="excluded">Excluded</option>
        </Select>
        <div className="relative min-w-60 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
          <TextInput aria-label="Search sources" placeholder="Search title, domain or lesson" value={q} onChange={(e) => setQ(e.target.value)} className="pl-9" />
        </div>
      </div>
      {error && <Alert tone="bad">{error.message}</Alert>}
      {loading && !data ? (
        <Spinner />
      ) : !data?.sources.length ? (
        <Card>
          <EmptyState icon={<Library className="size-5" />} title="No sources found">
            Sources appear here after you run research on a lesson.
          </EmptyState>
        </Card>
      ) : (
        <div className="grid gap-3">
          <p className="text-xs text-muted">{data.sources.length} source{data.sources.length === 1 ? '' : 's'}</p>
          {data.sources.map((s) => (
            <SourceCard
              key={s.id}
              source={s}
              extra={
                <p className="mt-2 text-xs text-muted">
                  Collected for <Link to={`/lessons/${s.lesson_id}`} className="text-accent hover:underline">{s.lesson_title}</Link>
                </p>
              }
            />
          ))}
        </div>
      )}
    </>
  )
}
