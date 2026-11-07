import type { EvidenceStatus, Severity } from '../types/api'

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return ''
  const diff = (Date.now() - new Date(iso).getTime()) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`
  return formatDate(iso)
}

export type Tone = 'neutral' | 'accent' | 'ok' | 'warn' | 'bad' | 'info'

export const evidenceTone: Record<EvidenceStatus, Tone> = {
  Supported: 'ok',
  'Partially Supported': 'warn',
  Unsupported: 'bad',
  'Conflicting Evidence': 'bad',
  'Unable to Verify': 'info',
}

export const severityTone: Record<Severity, Tone> = {
  Critical: 'bad',
  High: 'bad',
  Medium: 'warn',
  Low: 'info',
  Informational: 'neutral',
}

export const SEVERITIES: Severity[] = ['Critical', 'High', 'Medium', 'Low', 'Informational']

export function humanize(s: string): string {
  return s.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())
}

export function scoreTone(score: number | null | undefined): Tone {
  if (score == null) return 'neutral'
  if (score >= 80) return 'ok'
  if (score >= 60) return 'warn'
  return 'bad'
}
