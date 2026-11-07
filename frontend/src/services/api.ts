// Thin, typed API client. All requests go to the same-origin /api path
// (proxied to Flask in development), so no backend URL or secret lives here.
import type {
  ClaimWithSources,
  ExportFormat,
  LessonContent,
  LessonDetail,
  LessonSummary,
  LessonVersion,
  PublicConfig,
  Recommendation,
  ReportSummary,
  ResearchResult,
  ResearchSource,
  Stats,
  TimingReport,
} from '../types/api'

const BASE = '/api'

export class ApiError extends Error {
  status: number
  code: string
  details: unknown

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response
  try {
    res = await fetch(BASE + path, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init.headers ?? {}) },
    })
  } catch {
    throw new ApiError(0, 'network_error', 'Cannot reach the LessonForge server. Is the backend running?')
  }
  if (!res.ok) {
    let body: { error?: { code?: string; message?: string; details?: unknown } } = {}
    try {
      body = await res.json()
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(
      res.status,
      body.error?.code ?? 'http_error',
      body.error?.message ?? `Request failed (${res.status}).`,
      body.error?.details,
    )
  }
  return (await res.json()) as T
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

export interface LessonInput {
  title: string
  learning_objective: string
  audience?: string
  difficulty: 'Beginner' | 'Intermediate' | 'Advanced'
  delivery_mode: 'Self-learning' | 'Instructor-led'
  additional_instructions?: string
}

export interface SaveResult {
  action: 'unchanged' | 'updated' | 'created'
  version: LessonVersion
  lesson: LessonDetail
}

export const api = {
  health: () => request<{ status: string; config: PublicConfig }>('/health'),
  settings: () => request<PublicConfig>('/settings'),
  stats: () => request<Stats>('/stats'),

  listLessons: (q = '') => request<{ lessons: LessonSummary[] }>(`/lessons${q ? `?q=${encodeURIComponent(q)}` : ''}`),
  getLesson: (id: number) => request<LessonDetail>(`/lessons/${id}`),
  createLesson: (input: LessonInput) => post<LessonDetail>('/lessons', input),
  updateLesson: (id: number, input: Partial<LessonInput>) =>
    request<LessonDetail>(`/lessons/${id}`, { method: 'PUT', body: JSON.stringify(input) }),
  deleteLesson: (id: number) => request<{ deleted: number }>(`/lessons/${id}`, { method: 'DELETE' }),
  duplicateLesson: (id: number) => post<LessonDetail>(`/lessons/${id}/duplicate`),

  analyzeObjective: (id: number) => post<LessonDetail>(`/lessons/${id}/analyze-objective`),
  research: (id: number, providers?: string[]) =>
    post<{ research: ResearchResult; lesson: LessonDetail }>(`/lessons/${id}/research`, providers ? { providers } : {}),
  generate: (id: number, confirmOverwrite = false) =>
    post<{ timing: TimingReport; lesson: LessonDetail }>(`/lessons/${id}/generate`, {
      confirm_overwrite: confirmOverwrite,
    }),
  validateTiming: (id: number) => post<{ timing: TimingReport; lesson: LessonDetail }>(`/lessons/${id}/validate-timing`),
  runQC: (id: number, kind: 'factual' | 'instructional') =>
    post<{ report: ReportSummary; lesson: LessonDetail }>(`/lessons/${id}/qc/${kind}`),

  sources: (id: number) => request<{ sources: ResearchSource[] }>(`/lessons/${id}/sources`),
  library: (params: { type?: string; q?: string; evidence_use?: string }) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v) as [string, string][])
    return request<{ sources: ResearchSource[] }>(`/sources?${qs}`)
  },
  claims: (id: number) =>
    request<{ claims: ClaimWithSources[]; qc_review: { report_id: number; version_number: number; stale: boolean } | null }>(
      `/lessons/${id}/claims`,
    ),
  flagClaim: (id: number, claimId: string, needsResearch: boolean) =>
    request<LessonDetail>(`/lessons/${id}/claims/${claimId}`, {
      method: 'PATCH',
      body: JSON.stringify({ needs_research: needsResearch }),
    }),

  reports: (id: number) => request<{ reports: ReportSummary[] }>(`/lessons/${id}/reports`),
  recommendations: (id: number) => request<{ recommendations: Recommendation[] }>(`/lessons/${id}/recommendations`),
  applyRecommendation: (id: number, recId: number) =>
    post<{ result: { version_number: number; section_id: string; method: string; change_summary: string }; lesson: LessonDetail }>(
      `/lessons/${id}/recommendations/${recId}/apply`,
    ),
  rejectRecommendation: (id: number, recId: number) => post(`/lessons/${id}/recommendations/${recId}/reject`),
  reviewRecommendation: (id: number, recId: number) => post(`/lessons/${id}/recommendations/${recId}/review`),
  undoRecommendation: (id: number, recId: number) =>
    post<{ lesson: LessonDetail }>(`/lessons/${id}/recommendations/${recId}/undo`),

  saveContent: (id: number, content: LessonContent, opts: { autosave?: boolean; createVersion?: boolean; description?: string }) =>
    request<SaveResult>(`/lessons/${id}/content`, {
      method: 'PUT',
      body: JSON.stringify({
        content,
        autosave: !!opts.autosave,
        create_version: !!opts.createVersion,
        change_description: opts.description ?? (opts.autosave ? 'Instructor edit (autosave)' : 'Instructor edit'),
      }),
    }),
  versions: (id: number) => request<{ versions: LessonVersion[]; current_version_id: number; finalized_version_id: number | null }>(`/lessons/${id}/versions`),
  getVersion: (id: number, versionId: number) => request<LessonVersion & { content: LessonContent }>(`/lessons/${id}/versions/${versionId}`),
  restoreVersion: (id: number, versionId: number) => post<{ lesson: LessonDetail }>(`/lessons/${id}/versions/${versionId}/restore`),

  finalize: (id: number, acknowledgeWarnings = false) =>
    post<LessonDetail>(`/lessons/${id}/finalize`, { acknowledge_warnings: acknowledgeWarnings }),
  exportPreflight: (id: number) =>
    request<{ ready: boolean; version_number?: number; warnings: string[] }>(`/lessons/${id}/export/preflight`),

  /** Downloads an export and triggers a browser save. */
  async download(id: number, format: ExportFormat): Promise<string> {
    let res: Response
    try {
      res = await fetch(`${BASE}/lessons/${id}/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ format }),
      })
    } catch {
      throw new ApiError(0, 'network_error', 'Cannot reach the LessonForge server.')
    }
    if (!res.ok) {
      let message = `Export failed (${res.status}).`
      try {
        message = (await res.json()).error?.message ?? message
      } catch {
        /* ignore */
      }
      throw new ApiError(res.status, 'export_failed', message)
    }
    const disposition = res.headers.get('Content-Disposition') ?? ''
    const filename = /filename="?([^";]+)"?/.exec(disposition)?.[1] ?? `lesson-${id}.${format}`
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    return filename
  },
}
