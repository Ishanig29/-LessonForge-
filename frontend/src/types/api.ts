// Types mirror the Flask API responses (see backend/app/routes/serializers.py).

export type LessonStatus = 'Draft' | 'Researching' | 'Generated' | 'QC Reviewed' | 'Finalized'
export type StepStatus = 'Pending' | 'Running' | 'Completed' | 'Failed' | 'Retrying'
export type EvidenceStatus =
  | 'Supported'
  | 'Partially Supported'
  | 'Unsupported'
  | 'Conflicting Evidence'
  | 'Unable to Verify'
export type Severity = 'Critical' | 'High' | 'Medium' | 'Low' | 'Informational'
export type SourceType = 'website' | 'book' | 'youtube'
export type EvidenceUse = 'evidence' | 'supplementary' | 'further_reading' | 'excluded'
export type SectionKind =
  | 'introduction'
  | 'prerequisites'
  | 'concept'
  | 'worked_example'
  | 'application'
  | 'activity'
  | 'knowledge_check'
  | 'answers'
  | 'takeaways'
  | 'summary'

export interface LessonSection {
  id: string
  kind: SectionKind
  title: string
  duration_minutes: number
  activity: string
  content: string
}

export interface KnowledgeCheckQuestion {
  id: string
  question: string
  kind: 'multiple_choice' | 'short_answer' | 'practical'
  options: string[]
  answer: string
  explanation: string
  outcome_ids: string[]
}

export interface LessonClaim {
  id: string
  text: string
  section_id: string
  source_ids: string[]
  evidence_excerpt: string | null
  status: EvidenceStatus | null
  verification_note: string | null
  needs_research: boolean
}

export interface LessonContent {
  title: string
  learning_objective: string
  learning_outcomes: string[]
  target_audience: string
  assumed_knowledge: string
  sections: LessonSection[]
  knowledge_check: KnowledgeCheckQuestion[]
  claims: LessonClaim[]
  supplementary_video_ids: string[]
  reference_ids: string[]
}

export interface LessonVersion {
  id: number
  version_number: number
  origin: string
  change_description: string
  duration_minutes: number
  content_hash: string
  created_at: string
  updated_at: string
  content?: LessonContent
}

export interface WorkflowStep {
  name: string
  label: string
  status: StepStatus
  error_message: string | null
  error_code: string | null
  retry_count: number
  summary: Record<string, unknown> | null
  started_at: string | null
  completed_at: string | null
}

export interface TimingReport {
  total_minutes: number
  limit_minutes: number
  compliant: boolean
  over_by: number
  issues: string[]
  by_category: Record<string, number>
  sections: { id: string; title: string; kind: string; duration_minutes: number; activity: string }[]
  revision_rounds?: { round: number; before: number; after: number; changes: { id: string; from: number; to: number }[] }[]
}

export interface ReportSummary {
  id: number
  qc_type: 'factual' | 'instructional'
  score: number | null
  status: string
  version_number: number | null
  lesson_version_id: number | null
  model: string | null
  is_demo: boolean
  created_at: string
  stale: boolean
  stale_reason: string | null
  report?: QCReportBody
}

export interface LearningOutcome {
  id: string
  outcome: string
  bloom_level: string
  measurable_by: string
}

export interface ObjectiveAnalysis {
  interpretation: string
  original_objective: string
  learners_should_understand: string[]
  learners_should_be_able_to: string[]
  key_concepts: string[]
  expected_difficulty: string
  prerequisites: string[]
  assessment_methods: string[]
  learning_outcomes: LearningOutcome[]
  search_queries: string[]
}

export interface QCSummary {
  score: number
  stale: boolean
  version_number: number
}

export interface LessonSummary {
  id: number
  title: string
  learning_objective: string
  status: LessonStatus
  difficulty: string
  delivery_mode: string
  audience: string | null
  is_demo: boolean
  created_at: string
  updated_at: string
  current_version_number: number | null
  duration_minutes: number | null
  qc: { factual: QCSummary | null; instructional: QCSummary | null }
  source_count: number
}

export interface LessonDetail extends LessonSummary {
  additional_instructions: string | null
  objective_analysis: ObjectiveAnalysis | null
  current_version: (LessonVersion & { content: LessonContent }) | null
  finalized_version_id: number | null
  is_current_finalized: boolean
  timing: TimingReport | null
  workflow: WorkflowStep[]
  latest_reports: { factual: ReportSummary | null; instructional: ReportSummary | null }
  source_counts: Record<SourceType, number>
  evidence_source_count: number
}

export interface ResearchSource {
  id: number
  source_id: string
  lesson_id: number
  lesson_title?: string
  source_type: SourceType
  provider: string
  title: string
  url: string | null
  author_or_domain: string | null
  description: string | null
  published_date: string | null
  retrieved_at: string
  query: string | null
  reliability_score: number
  reliability_tier: string
  reliability_rationale: string | null
  evidence_use: EvidenceUse
  has_retrieved_text: boolean
  content_length: number
  metadata: Record<string, unknown>
  is_demo: boolean
  passages: string[]
  content_excerpt?: string | null
}

export interface ProviderReport {
  provider: string
  source_type: SourceType
  queries: string[]
  status: 'ok' | 'partial' | 'failed' | 'empty'
  found: number
  error: string | null
  error_code: string | null
}

export interface ResearchResult {
  providers: ProviderReport[]
  added: number
  updated: number
  duplicates_removed: number
  total_sources: number
  evidence_sources: number
}

export interface ClaimWithSources extends LessonClaim {
  sources: {
    source_id: string
    title: string
    url: string | null
    source_type: SourceType
    reliability_tier: string
    evidence_use: EvidenceUse
  }[]
  qc_status: EvidenceStatus | null
  qc_rationale: string | null
}

export interface RubricRow {
  criterion: string
  description: string
  max: number
  score: number
  rationale: string
}

export interface QCIssue {
  id: string
  severity: Severity
  category: string
  section_id: string | null
  claim_id: string | null
  explanation: string
  evidence_or_reason: string
  suggested_improvement: string
  suggested_text: string | null
  origin: 'automated' | 'evaluator'
}

export interface AreaFinding {
  summary: string
  strengths: string[]
  concerns: string[]
}

export interface QCReportBody {
  qc_type: 'factual' | 'instructional'
  title: string
  overall_assessment: string
  score: number
  score_max: number
  rubric: RubricRow[]
  score_disclaimer: string
  issues: QCIssue[]
  severity_counts: Record<Severity, number>
  // factual
  claims_reviewed?: number
  claim_counts?: Record<string, number>
  claims?: {
    claim_id: string
    section_id: string
    text: string
    source_ids: string[]
    automated_status: EvidenceStatus
    evaluator_status: EvidenceStatus
    final_status: EvidenceStatus
    rationale: string
  }[]
  source_findings?: { source_id: string; authority: string; is_primary: boolean; relevant: boolean; note: string }[]
  missing_important_facts?: string[]
  suggested_additional_research?: string[]
  // instructional
  findings?: Record<string, AreaFinding>
  outcome_coverage?: { outcome: string; covered: boolean; where: string[]; note: string }[]
  timing?: { total_minutes: number; limit_minutes: number; compliant: boolean; by_category: Record<string, number>; issues: string[] }
}

export interface Recommendation {
  id: number
  qc_report_id: number
  qc_type: 'factual' | 'instructional'
  report_version_number: number
  report_stale: boolean
  from_latest_report: boolean
  issue_key: string
  affected_section_id: string | null
  claim_key: string | null
  issue: string
  why_it_matters: string | null
  suggested_change: string
  suggested_text: string | null
  severity: Severity
  review_status: 'pending' | 'accepted' | 'rejected' | 'reviewed' | 'undone'
  applied_at: string | null
  reviewed_at: string | null
  applied_version_id: number | null
  can_undo: boolean
}

export interface IntegrationStatus {
  configured: boolean
  env_var: string
  has_key?: boolean
  note?: string
}

export interface PublicConfig {
  ai_provider: string
  ai_model: string
  demo_mode: boolean
  max_lesson_minutes: number
  integrations: Record<'gemini' | 'tavily' | 'google_books' | 'youtube', IntegrationStatus>
}

export interface Stats {
  lessons_total: number
  lessons_by_status: Record<LessonStatus, number>
  sources_by_type: Partial<Record<SourceType, number>>
}

export type ExportFormat =
  | 'lesson_pdf'
  | 'lesson_markdown'
  | 'references_json'
  | 'references_csv'
  | 'qc_factual_pdf'
  | 'qc_factual_json'
  | 'qc_factual_markdown'
  | 'qc_instructional_pdf'
  | 'qc_instructional_json'
  | 'qc_instructional_markdown'
  | 'zip'
