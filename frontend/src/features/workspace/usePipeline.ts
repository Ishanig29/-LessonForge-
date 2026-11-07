import { useCallback, useRef, useState } from 'react'
import { errorMessage } from '../../hooks/useAsync'
import { api, ApiError } from '../../services/api'
import type { LessonDetail } from '../../types/api'

export type StageKey = 'analysis' | 'research' | 'generate' | 'qc_factual' | 'qc_instructional'

/** Which backend workflow steps each stage call executes (used to show "Running"). */
export const STAGE_STEPS: Record<StageKey, string[]> = {
  analysis: ['objective_analysis'],
  research: ['research', 'source_evaluation'],
  generate: ['evidence_extraction', 'lesson_generation', 'timing_validation'],
  qc_factual: ['qc_factual'],
  qc_instructional: ['qc_instructional'],
}

export const STEP_TO_STAGE: Record<string, StageKey> = Object.fromEntries(
  Object.entries(STAGE_STEPS).flatMap(([stage, steps]) => steps.map((s) => [s, stage as StageKey])),
)

const ORDER: StageKey[] = ['analysis', 'research', 'generate', 'qc_factual', 'qc_instructional']

/**
 * Runs workflow stages against the backend. Progress shown in the UI comes
 * from the backend's step records; the only client-side state is which request
 * is currently in flight.
 */
export function usePipeline(lessonId: number, onLesson: (l: LessonDetail) => void) {
  const [running, setRunning] = useState<StageKey | null>(null)
  const [error, setError] = useState<{ stage: StageKey; message: string } | null>(null)
  const [needsOverwriteConfirm, setNeedsOverwriteConfirm] = useState(false)
  const cancelRef = useRef(false)

  const runStage = useCallback(
    async (stage: StageKey, opts: { confirmOverwrite?: boolean } = {}): Promise<LessonDetail | null> => {
      setRunning(stage)
      setError(null)
      try {
        let lesson: LessonDetail
        switch (stage) {
          case 'analysis':
            lesson = await api.analyzeObjective(lessonId)
            break
          case 'research':
            lesson = (await api.research(lessonId)).lesson
            break
          case 'generate':
            lesson = (await api.generate(lessonId, opts.confirmOverwrite)).lesson
            break
          case 'qc_factual':
            lesson = (await api.runQC(lessonId, 'factual')).lesson
            break
          case 'qc_instructional':
            lesson = (await api.runQC(lessonId, 'instructional')).lesson
            break
        }
        onLesson(lesson)
        return lesson
      } catch (e) {
        if (e instanceof ApiError && e.code === 'confirm_overwrite_required') {
          setNeedsOverwriteConfirm(true)
        } else {
          setError({ stage, message: errorMessage(e) })
        }
        // Refresh so the failed step's persisted status and message are shown.
        try {
          onLesson(await api.getLesson(lessonId))
        } catch {
          /* keep current view */
        }
        return null
      } finally {
        setRunning(null)
      }
    },
    [lessonId, onLesson],
  )

  /** Run every stage from `from` onwards, stopping at the first failure. */
  const runFrom = useCallback(
    async (from: StageKey = 'analysis', opts: { confirmOverwrite?: boolean } = {}) => {
      cancelRef.current = false
      for (const stage of ORDER.slice(ORDER.indexOf(from))) {
        if (cancelRef.current) break
        const lesson = await runStage(stage, stage === 'generate' ? opts : {})
        if (!lesson) return false
        if (stage === 'research') {
          const step = lesson.workflow.find((s) => s.name === 'research')
          if (step?.status === 'Failed') {
            setError({ stage, message: step.error_message ?? 'Research failed.' })
            return false
          }
        }
        if (stage === 'qc_factual') continue // a QC failure never blocks the other layer
      }
      return true
    },
    [runStage],
  )

  return {
    running,
    error,
    clearError: () => setError(null),
    runStage,
    runFrom,
    stop: () => {
      cancelRef.current = true
    },
    needsOverwriteConfirm,
    setNeedsOverwriteConfirm,
  }
}
