import { CheckCircle2, CircleAlert, KeyRound } from 'lucide-react'
import { Alert, Badge, Card, CardHeader, PageHeader, Spinner } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { api } from '../services/api'

const INTEGRATIONS = [
  { key: 'gemini', name: 'Gemini', purpose: 'Objective analysis, lesson generation and both QC evaluators.' },
  { key: 'tavily', name: 'Tavily Search', purpose: 'Web research. The only source of verifiable evidence text.' },
  { key: 'google_books', name: 'Google Books', purpose: 'Book discovery (metadata only; books are recommended as further reading).' },
  { key: 'youtube', name: 'YouTube Data API', purpose: 'Supplementary videos (metadata only; transcripts are not read).' },
] as const

export default function Settings() {
  const { data, loading, error } = useAsync(() => api.health(), [])
  const config = data?.config
  return (
    <>
      <PageHeader title="Settings & API configuration" subtitle="Keys live only in backend/.env on your machine. This page shows whether each one is present, never its value." />
      {error && <Alert tone="bad" title="Backend unreachable">{error.message}</Alert>}
      {loading && !data && <Spinner />}
      {config && (
        <div className="space-y-6">
          {config.demo_mode && (
            <Alert tone="warn" title="Offline demo mode is on">
              Research uses labelled fixture text captured from real documentation, and the "AI" steps use a rule-based stand-in.
              Demo lessons are marked everywhere they appear. Set <code>DEMO_MODE=false</code> in backend/.env for live use.
            </Alert>
          )}
          <Card>
            <CardHeader title="Integrations" description={`AI provider: ${config.ai_provider} · model ${config.ai_model}`} />
            <ul className="divide-y divide-line">
              {INTEGRATIONS.map((i) => {
                const s = config.integrations[i.key]
                return (
                  <li key={i.key} className="flex flex-wrap items-center gap-4 px-5 py-4">
                    {s.configured ? <CheckCircle2 className="size-5 text-ok" aria-hidden /> : <CircleAlert className="size-5 text-warn" aria-hidden />}
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-ink">{i.name}</p>
                      <p className="text-[13px] text-muted">{i.purpose}</p>
                      {s.note && <p className="mt-0.5 text-xs text-muted">{s.note}</p>}
                    </div>
                    <code className="inline-flex items-center gap-1.5 rounded bg-paper-2 px-2 py-1 text-xs text-ink-2">
                      <KeyRound className="size-3" aria-hidden />{s.env_var}
                    </code>
                    <Badge tone={s.configured ? 'ok' : 'warn'}>{s.configured ? (s.has_key === false ? 'Works without key' : 'Configured') : 'Missing'}</Badge>
                  </li>
                )
              })}
            </ul>
          </Card>
          <Card className="p-5 text-sm text-ink-2">
            <h2 className="mb-2 font-semibold text-ink">How to add a key</h2>
            <ol className="list-decimal space-y-1 pl-5">
              <li>Copy <code>backend/.env.example</code> to <code>backend/.env</code>.</li>
              <li>Paste each key after its variable name, e.g. <code>GEMINI_API_KEY=…</code>.</li>
              <li>Restart the backend (<code>python run.py</code>) and reload this page.</li>
            </ol>
            <p className="mt-3 text-xs text-muted">Lessons are limited to {config.max_lesson_minutes} minutes; this rule is enforced by the backend.</p>
          </Card>
        </div>
      )}
    </>
  )
}
