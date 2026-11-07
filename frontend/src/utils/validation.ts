// Client-side checks mirror backend limits (backend/app/schemas/lesson.py) so users
// get immediate, friendly feedback. The backend validates independently.
export const LIMITS = {
  titleMin: 3,
  titleMax: 200,
  objectiveMin: 10,
  objectiveMax: 1000,
  audienceMax: 300,
  instructionsMax: 2000,
}

export interface LessonFormValues {
  title: string
  learning_objective: string
  audience: string
  additional_instructions: string
}

export type FormErrors = Partial<Record<keyof LessonFormValues, string>>

export function validateLessonForm(v: LessonFormValues): FormErrors {
  const errors: FormErrors = {}
  const title = v.title.trim()
  const objective = v.learning_objective.trim()
  if (!title) errors.title = 'Give the lesson a title.'
  else if (title.length < LIMITS.titleMin) errors.title = `The title needs at least ${LIMITS.titleMin} characters.`
  else if (title.length > LIMITS.titleMax)
    errors.title = `Keep the title under ${LIMITS.titleMax} characters (currently ${title.length}).`

  if (!objective) errors.learning_objective = 'Describe what learners should achieve.'
  else if (objective.length < LIMITS.objectiveMin)
    errors.learning_objective = 'The objective is too short to research. Add what learners should be able to do.'
  else if (objective.length > LIMITS.objectiveMax)
    errors.learning_objective = `Keep the objective under ${LIMITS.objectiveMax} characters (currently ${objective.length}). Split very broad objectives into separate lessons.`

  if (v.audience.length > LIMITS.audienceMax)
    errors.audience = `Keep the audience description under ${LIMITS.audienceMax} characters.`
  if (v.additional_instructions.length > LIMITS.instructionsMax)
    errors.additional_instructions = `Keep instructions under ${LIMITS.instructionsMax} characters.`
  return errors
}
