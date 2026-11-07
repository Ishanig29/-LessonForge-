import { Download, FileArchive, FileJson, FileText, History, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { Alert, Badge, Button, Card, CardHeader, ConfirmDialog, EmptyState, Spinner } from '../../components/ui'
import { errorMessage, useAsync } from '../../hooks/useAsync'
import type { WorkspaceProps } from '../../pages/LessonWorkspace'
import { api } from '../../services/api'
import type { ExportFormat, LessonVersion } from '../../types/api'
import { formatDateTime, humanize } from '../../utils/format'

const GROUPS: { title: string; items: { format: ExportFormat; label: string; needs?: 'factual' | 'instructional' }[] }[] = [
  { title: 'Lesson', items: [{ format: 'lesson_pdf', label: 'PDF' }, { format: 'lesson_markdown', label: 'Markdown' }] },
  { title: 'Research references', items: [{ format: 'references_json', label: 'JSON' }, { format: 'references_csv', label: 'CSV' }] },
  {
    title: 'QC Layer 1 · Factual accuracy report',
    items: [{ format: 'qc_factual_pdf', label: 'PDF', needs: 'factual' }, { format: 'qc_factual_markdown', label: 'Markdown', needs: 'factual' }, { format: 'qc_factual_json', label: 'JSON', needs: 'factual' }],
  },
  {
    title: 'QC Layer 2 · Instructional quality report',
    items: [{ format: 'qc_instructional_pdf', label: 'PDF', needs: 'instructional' }, { format: 'qc_instructional_markdown', label: 'Markdown', needs: 'instructional' }, { format: 'qc_instructional_json', label: 'JSON', needs: 'instructional' }],
  },
]

export default function ExportTab({ lesson, setLesson }: WorkspaceProps) {
  const preflight = useAsync(() => api.exportPreflight(lesson.id), [lesson.id, lesson.current_version?.content_hash, lesson.status, lesson.latest_reports.factual?.id, lesson.latest_reports.instructional?.id])
  const versions = useAsync(() => api.versions(lesson.id), [lesson.id, lesson.current_version?.id, lesson.current_version?.updated_at])
  const [busy, setBusy] = useState<string | null>(null)
  const [message, setMessage] = useState<{ tone: 'ok' | 'bad'; text: string } | null>(null)
  const [restore, setRestore] = useState<LessonVersion | null>(null)

  const download = async (format: ExportFormat) => {
    setBusy(format)
    setMessage(null)
    try {
      const name = await api.download(lesson.id, format)
      setMessage({ tone: 'ok', text: `Downloaded ${name}` })
    } catch (e) {
      setMessage({ tone: 'bad', text: errorMessage(e) })
    } finally {
      setBusy(null)
    }
  }

  const doRestore = async () => {
    if (!restore) return
    setBusy(`restore-${restore.id}`)
    try {
      setLesson((await api.restoreVersion(lesson.id, restore.id)).lesson)
      setRestore(null)
      setMessage({ tone: 'ok', text: `Version ${restore.version_number} restored as a new version.` })
    } catch (e) {
      setMessage({ tone: 'bad', text: errorMessage(e) })
    } finally {
      setBusy(null)
    }
  }

  if (!lesson.current_version) {
    return <Card><EmptyState title="Nothing to export yet">Generate the lesson first.</EmptyState></Card>
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.2fr_1fr]">
      <div className="space-y-6">
        {preflight.data && preflight.data.warnings.length > 0 && (
          <Alert tone="warn" title="Before you export">
            <ul className="list-disc pl-4">{preflight.data.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
            <p className="mt-1">These statuses are printed inside every exported file.</p>
          </Alert>
        )}
        {message && <Alert tone={message.tone}>{message.text}</Alert>}
        <Card>
          <CardHeader
            title="Complete package"
            description={`ZIP with lesson PDF + Markdown, references, both QC reports and a manifest. Version ${lesson.current_version.version_number}.`}
            action={<Button variant="primary" loading={busy === 'zip'} onClick={() => void download('zip')} icon={<FileArchive className="size-4" />}>Download ZIP</Button>}
          />
        </Card>
        <Card>
          <CardHeader title="Individual files" />
          <ul className="divide-y divide-line">
            {GROUPS.map((g) => (
              <li key={g.title} className="flex flex-wrap items-center gap-3 px-5 py-3.5">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-ink">{g.title}</p>
                  {g.items[0].needs && (() => {
                    const r = lesson.latest_reports[g.items[0].needs!]
                    return <p className="text-xs text-muted">{!r ? 'Not run yet' : r.stale ? `Evaluated version ${r.version_number} (stale)` : `Evaluated version ${r.version_number}`}</p>
                  })()}
                </div>
                <div className="flex gap-1.5">
                  {g.items.map((it) => {
                    const missing = it.needs && !lesson.latest_reports[it.needs]
                    return (
                      <Button key={it.format} size="sm" disabled={!!missing} loading={busy === it.format} onClick={() => void download(it.format)}
                        icon={it.label === 'JSON' ? <FileJson className="size-3.5" /> : it.label === 'PDF' ? <Download className="size-3.5" /> : <FileText className="size-3.5" />}>
                        {it.label}
                      </Button>
                    )
                  })}
                </div>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card>
        <CardHeader title={<span className="flex items-center gap-2"><History className="size-4" /> Version history</span>} description="Every version is kept. Restoring creates a new version." />
        {versions.loading && !versions.data ? <Spinner /> : (
          <ol className="divide-y divide-line">
            {versions.data?.versions.map((v) => (
              <li key={v.id} className="flex items-start gap-3 px-5 py-3">
                <span className="mt-0.5 font-mono text-xs font-semibold text-ink">v{v.version_number}</span>
                <div className="min-w-0 flex-1 text-[13px]">
                  <div className="flex flex-wrap gap-1.5">
                    <Badge>{humanize(v.origin)}</Badge>
                    {v.id === versions.data!.current_version_id && <Badge tone="accent">Current</Badge>}
                    {v.id === versions.data!.finalized_version_id && <Badge tone="ok">Finalized</Badge>}
                    <span className="text-xs text-muted">{v.duration_minutes} min</span>
                  </div>
                  <p className="mt-1 text-ink-2">{v.change_description}</p>
                  <p className="text-xs text-muted">{formatDateTime(v.updated_at)}</p>
                </div>
                {v.id !== versions.data!.current_version_id && (
                  <Button size="sm" variant="ghost" onClick={() => setRestore(v)} icon={<RotateCcw className="size-3.5" />}>Restore</Button>
                )}
              </li>
            ))}
          </ol>
        )}
      </Card>

      <ConfirmDialog open={!!restore} title={`Restore version ${restore?.version_number}?`} confirmLabel="Restore as new version" loading={busy?.startsWith('restore')} onCancel={() => setRestore(null)} onConfirm={() => void doRestore()}>
        The content of version {restore?.version_number} becomes a new current version. Nothing is deleted, and existing QC reports will be marked stale if the content differs.
      </ConfirmDialog>
    </div>
  )
}
