import { act, fireEvent, render, renderHook, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { LessonMarkdown } from '../components/LessonMarkdown'
import { ScoreBadge } from '../components/StatusBadges'
import { useAutosave } from '../hooks/useAutosave'
import CreateLesson from '../pages/CreateLesson'
import { api, ApiError } from '../services/api'
import { validateLessonForm } from '../utils/validation'

const empty = { title: '', learning_objective: '', audience: '', additional_instructions: '' }

describe('validateLessonForm', () => {
  it('requires title and objective', () => {
    const e = validateLessonForm(empty)
    expect(e.title).toMatch(/title/i)
    expect(e.learning_objective).toBeTruthy()
  })
  it('rejects overly long input with the current length', () => {
    const e = validateLessonForm({ ...empty, title: 'x'.repeat(201), learning_objective: 'y'.repeat(1001) })
    expect(e.title).toContain('201')
    expect(e.learning_objective).toContain('1001')
  })
  it('accepts a valid lesson', () => {
    expect(validateLessonForm({ ...empty, title: 'HTTP', learning_objective: 'Explain GET and POST.' })).toEqual({})
  })
})

describe('CreateLesson form', () => {
  afterEach(() => vi.restoreAllMocks())

  it('shows friendly errors and does not call the API when invalid', async () => {
    const spy = vi.spyOn(api, 'createLesson')
    render(<MemoryRouter><CreateLesson /></MemoryRouter>)
    await userEvent.click(screen.getByRole('button', { name: /generate lesson/i }))
    expect(screen.getByText('Give the lesson a title.')).toBeInTheDocument()
    expect(screen.getByLabelText(/lesson title/i)).toHaveAttribute('aria-invalid', 'true')
    expect(spy).not.toHaveBeenCalled()
  })

  it('submits trimmed values', async () => {
    const spy = vi.spyOn(api, 'createLesson').mockResolvedValue({ id: 7 } as never)
    render(<MemoryRouter><CreateLesson /></MemoryRouter>)
    await userEvent.type(screen.getByLabelText(/lesson title/i), '  HTTP basics  ')
    await userEvent.type(screen.getByLabelText(/learning objective/i), 'Explain GET and POST methods.')
    await userEvent.click(screen.getByRole('button', { name: /generate lesson/i }))
    expect(spy).toHaveBeenCalledWith(expect.objectContaining({ title: 'HTTP basics', difficulty: 'Beginner', audience: undefined }))
  })

  it('shows backend validation errors on the matching field', async () => {
    vi.spyOn(api, 'createLesson').mockRejectedValue(
      new ApiError(422, 'validation_error', 'Some fields are invalid.', [{ field: 'title', message: 'Too short from server' }]),
    )
    render(<MemoryRouter><CreateLesson /></MemoryRouter>)
    await userEvent.type(screen.getByLabelText(/lesson title/i), 'HTTP basics')
    await userEvent.type(screen.getByLabelText(/learning objective/i), 'Explain GET and POST methods.')
    await userEvent.click(screen.getByRole('button', { name: /generate lesson/i }))
    expect(await screen.findByText('Too short from server')).toBeInTheDocument()
  })
})

describe('useAutosave', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    localStorage.clear()
  })
  afterEach(() => vi.useRealTimers())

  it('debounces, saves once with the latest value and clears the local draft', async () => {
    const save = vi.fn().mockResolvedValue(undefined)
    const { result } = renderHook(() => useAutosave<string>({ save, storageKey: 'k', delay: 1000 }))
    act(() => {
      result.current.schedule('a')
      result.current.schedule('ab')
    })
    expect(result.current.state).toBe('dirty')
    expect(JSON.parse(localStorage.getItem('k')!).value).toBe('ab')
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    expect(save).toHaveBeenCalledTimes(1)
    expect(save).toHaveBeenCalledWith('ab')
    expect(result.current.state).toBe('saved')
    expect(localStorage.getItem('k')).toBeNull()
  })

  it('keeps the draft and reports failure when saving fails', async () => {
    const save = vi.fn().mockRejectedValue(new Error('offline'))
    const { result } = renderHook(() => useAutosave<string>({ save, storageKey: 'k2', delay: 500 }))
    act(() => result.current.schedule('draft'))
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500)
    })
    expect(result.current.state).toBe('error')
    expect(result.current.lastError).toBe('offline')
    expect(result.current.readDraft()?.value).toBe('draft')
  })
})

describe('presentation components', () => {
  it('marks stale QC scores', () => {
    render(<ScoreBadge score={82} stale />)
    expect(screen.getByText(/82\/100 · stale/)).toBeInTheDocument()
  })

  it('turns claim markers into evidence links', () => {
    const onClaim = vi.fn()
    render(<LessonMarkdown onClaimClick={onClaim}>{'GET is safe [C2].'}</LessonMarkdown>)
    fireEvent.click(screen.getByRole('button', { name: /evidence for claim C2/i }))
    expect(onClaim).toHaveBeenCalledWith('C2')
  })
})

describe('api client', () => {
  afterEach(() => vi.restoreAllMocks())

  it('converts backend error bodies into ApiError', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: 'missing_credentials', message: 'Set GEMINI_API_KEY' } }), { status: 503 })))
    await expect(api.analyzeObjective(1)).rejects.toMatchObject({ status: 503, code: 'missing_credentials', message: 'Set GEMINI_API_KEY' })
  })

  it('reports network failures clearly', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(api.getLesson(1)).rejects.toMatchObject({ code: 'network_error' })
  })
})
