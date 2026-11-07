import { Sparkles } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Alert, Button, Card, Field, PageHeader, Select, TextArea, TextInput } from '../components/ui'
import { errorMessage } from '../hooks/useAsync'
import { api, ApiError, type LessonInput } from '../services/api'
import { LIMITS, validateLessonForm, type FormErrors, type LessonFormValues } from '../utils/validation'

const EXAMPLES = [
  {
    title: 'HTTP Requests and Responses',
    learning_objective: 'Explain GET and POST methods and distinguish between 2xx, 4xx, and 5xx response status categories.',
  },
  {
    title: 'Introduction to SQL Joins',
    learning_objective:
      'Explain INNER JOIN, LEFT JOIN, RIGHT JOIN and FULL OUTER JOIN, and demonstrate how they combine records from two relational tables.',
  },
]

export default function CreateLesson() {
  const navigate = useNavigate()
  const [values, setValues] = useState<LessonFormValues>({ title: '', learning_objective: '', audience: '', additional_instructions: '' })
  const [difficulty, setDifficulty] = useState<LessonInput['difficulty']>('Beginner')
  const [mode, setMode] = useState<LessonInput['delivery_mode']>('Self-learning')
  const [errors, setErrors] = useState<FormErrors>({})
  const [submitting, setSubmitting] = useState(false)
  const [serverError, setServerError] = useState<string | null>(null)

  const set = (k: keyof LessonFormValues) => (e: { target: { value: string } }) => {
    setValues((v) => ({ ...v, [k]: e.target.value }))
    if (errors[k]) setErrors((er) => ({ ...er, [k]: undefined }))
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const found = validateLessonForm(values)
    setErrors(found)
    if (Object.keys(found).length) return
    setSubmitting(true)
    setServerError(null)
    try {
      const lesson = await api.createLesson({
        title: values.title.trim(),
        learning_objective: values.learning_objective.trim(),
        audience: values.audience.trim() || undefined,
        additional_instructions: values.additional_instructions.trim() || undefined,
        difficulty,
        delivery_mode: mode,
      })
      navigate(`/lessons/${lesson.id}?run=1`)
    } catch (err) {
      if (err instanceof ApiError && Array.isArray(err.details)) {
        const fieldErrors: FormErrors = {}
        for (const d of err.details as { field: string; message: string }[]) {
          fieldErrors[d.field as keyof FormErrors] = d.message
        }
        setErrors(fieldErrors)
      }
      setServerError(errorMessage(err))
      setSubmitting(false)
    }
  }

  return (
    <>
      <PageHeader title="Create a lesson" subtitle="Two fields are required. Everything else helps the lesson fit your learners." />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_280px]">
        <Card className="p-6">
          <form onSubmit={submit} noValidate className="space-y-5">
            {serverError && <Alert tone="bad" title="The lesson could not be created">{serverError}</Alert>}
            <Field label="Lesson title" required error={errors.title} counter={{ value: values.title.length, max: LIMITS.titleMax }}>
              {(p) => (
                <TextInput id={p.id} aria-describedby={p.describedBy} invalid={p.invalid} value={values.title} onChange={set('title')} placeholder="e.g. HTTP Requests and Responses" autoFocus />
              )}
            </Field>
            <Field
              label="Learning objective"
              required
              error={errors.learning_objective}
              hint="What should learners be able to do after the lesson? Your wording is kept exactly as written."
              counter={{ value: values.learning_objective.length, max: LIMITS.objectiveMax }}
            >
              {(p) => (
                <TextArea id={p.id} aria-describedby={p.describedBy} invalid={p.invalid} rows={3} value={values.learning_objective} onChange={set('learning_objective')} placeholder="e.g. Explain GET and POST methods and distinguish between 2xx, 4xx and 5xx status categories." />
              )}
            </Field>
            <div className="grid gap-5 sm:grid-cols-2">
              <Field label="Target learner" error={errors.audience}>
                {(p) => <TextInput id={p.id} aria-describedby={p.describedBy} invalid={p.invalid} value={values.audience} onChange={set('audience')} placeholder="e.g. First-year CS students" />}
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Difficulty" required>
                  {(p) => (
                    <Select id={p.id} value={difficulty} onChange={(e) => setDifficulty(e.target.value as LessonInput['difficulty'])}>
                      <option>Beginner</option>
                      <option>Intermediate</option>
                      <option>Advanced</option>
                    </Select>
                  )}
                </Field>
                <Field label="Delivery" required>
                  {(p) => (
                    <Select id={p.id} value={mode} onChange={(e) => setMode(e.target.value as LessonInput['delivery_mode'])}>
                      <option>Self-learning</option>
                      <option>Instructor-led</option>
                    </Select>
                  )}
                </Field>
              </div>
            </div>
            <Field label="Additional instructions" error={errors.additional_instructions} counter={{ value: values.additional_instructions.length, max: LIMITS.instructionsMax }}>
              {(p) => <TextArea id={p.id} aria-describedby={p.describedBy} invalid={p.invalid} rows={2} value={values.additional_instructions} onChange={set('additional_instructions')} placeholder="e.g. Use Python for code examples." />}
            </Field>
            <div className="flex items-center justify-between gap-3 border-t border-line pt-5">
              <p className="text-xs text-muted">Generation runs analysis, research, writing, timing and both quality checks. It usually takes a few minutes.</p>
              <Button type="submit" variant="primary" loading={submitting} icon={<Sparkles className="size-4" />}>
                Generate lesson
              </Button>
            </div>
          </form>
        </Card>
        <aside className="space-y-3">
          <p className="text-xs font-medium uppercase tracking-wide text-muted">Try a demonstration topic</p>
          {EXAMPLES.map((ex) => (
            <button
              key={ex.title}
              type="button"
              onClick={() => {
                setValues((v) => ({ ...v, ...ex }))
                setErrors({})
              }}
              className="w-full rounded-xl border border-line bg-card p-4 text-left shadow-soft hover:border-accent/40"
            >
              <p className="text-sm font-medium text-ink">{ex.title}</p>
              <p className="mt-1 text-xs text-muted">{ex.learning_objective}</p>
            </button>
          ))}
        </aside>
      </div>
    </>
  )
}
