import { useCallback, useEffect, useRef, useState } from 'react'

export type SaveState = 'idle' | 'dirty' | 'saving' | 'saved' | 'error'

export const AUTOSAVE_DELAY_MS = 1500

/**
 * Debounced autosave. Call `schedule(value)` on every change; `save` runs once
 * the user pauses for `delay` ms. While a save is in flight, newer changes are
 * queued and saved afterwards, so no edit is lost. Unsaved drafts are mirrored
 * to localStorage under `storageKey` so they survive a refresh or a failed save.
 */
export function useAutosave<T>({
  save,
  storageKey,
  delay = AUTOSAVE_DELAY_MS,
}: {
  save: (value: T) => Promise<void>
  storageKey: string
  delay?: number
}) {
  const [state, setState] = useState<SaveState>('idle')
  const [lastError, setLastError] = useState<string | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pending = useRef<T | null>(null)
  const inFlight = useRef(false)
  const saveRef = useRef(save)
  saveRef.current = save

  const writeDraft = (value: T | null) => {
    try {
      if (value === null) localStorage.removeItem(storageKey)
      else localStorage.setItem(storageKey, JSON.stringify({ savedAt: Date.now(), value }))
    } catch {
      /* storage may be unavailable; server autosave still works */
    }
  }

  const flush = useCallback(async () => {
    if (timer.current) {
      clearTimeout(timer.current)
      timer.current = null
    }
    if (inFlight.current || pending.current === null) return
    const value = pending.current
    pending.current = null
    inFlight.current = true
    setState('saving')
    try {
      await saveRef.current(value)
      setLastError(null)
      if (pending.current === null) {
        writeDraft(null)
        setState('saved')
      }
    } catch (e) {
      pending.current = pending.current ?? value
      setLastError(e instanceof Error ? e.message : 'Save failed')
      setState('error')
    } finally {
      inFlight.current = false
      if (pending.current !== null && timer.current === null) {
        timer.current = setTimeout(() => void flush(), delay)
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [delay, storageKey])

  const schedule = useCallback(
    (value: T) => {
      pending.current = value
      writeDraft(value)
      setState('dirty')
      if (timer.current) clearTimeout(timer.current)
      timer.current = setTimeout(() => void flush(), delay)
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [delay, flush, storageKey],
  )

  const readDraft = useCallback((): { savedAt: number; value: T } | null => {
    try {
      const raw = localStorage.getItem(storageKey)
      return raw ? JSON.parse(raw) : null
    } catch {
      return null
    }
  }, [storageKey])

  const discardDraft = useCallback(() => {
    pending.current = null
    writeDraft(null)
    setState('idle')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storageKey])

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current)
  }, [])

  return { state, lastError, schedule, flush, readDraft, discardDraft, hasPending: () => pending.current !== null || inFlight.current }
}
