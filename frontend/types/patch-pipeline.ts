export interface PatchPlan {
  plan_id: string
  input_type: string
  source: string
  description: string
  affected_areas: string[]
  estimated_files: number
  risk: string
  required_tests: string[]
  complexity: string
  status: string
  created_at: string
}

export interface PatchCandidate {
  candidate_id: string
  plan_id: string
  approach: string
  index: number
  files_changed: PatchFileChange[]
  reasoning: string
  confidence: number
  estimated_impact: {
    files: number
    lines_added: number
    lines_removed: number
  }
  status: string
  validation: ValidationResult | null
  score: number | null
  created_at: string
}

export interface PatchFileChange {
  path: string
  lines_added: number
  lines_removed: number
}

export interface ValidationResult {
  validation_id: string
  candidate_id: string
  sandbox_id: string
  status: string
  build: ValidationBuild | null
  tests: ValidationTests | null
  security: ValidationSecurity | null
  coverage: ValidationCoverage | null
  metrics: Record<string, number>
  error?: string
  started_at: string
  completed_at: string
}

export interface ValidationBuild {
  success: boolean
  exit_code: number
  output: string
  duration_ms: number
}

export interface ValidationTests {
  success: boolean
  exit_code: number
  passed: number
  failed: number
  total: number
  output: string
  duration_ms: number
}

export interface ValidationSecurity {
  vulnerabilities: number
  warnings: number
  passed: boolean
  scanner: string
}

export interface ValidationCoverage {
  line_coverage_pct: number
  branch_coverage_pct: number
  files_covered: number
}

export interface ComparisonResult {
  selected: {
    candidate_id: string
    approach: string
    score: number
    validation: ValidationResult | null
  } | null
  rankings: {
    rank: number
    candidate_id: string
    approach: string
    score: number
  }[]
  method: string
  compared_at: string
}

export interface RefactoringAnalysis {
  analysis_id: string
  directory: string
  files_analyzed: number
  findings: RefactoringFinding[]
  suggestions: RefactoringSuggestion[]
  summary: {
    total_findings: number
    by_type: Record<string, number>
    by_severity: Record<string, number>
  }
  analyzed_at: string
}

export interface RefactoringFinding {
  type: string
  severity: string
  file: string
  line: number
  message: string
  suggestion: string
}

export interface RefactoringSuggestion {
  type: string
  file: string
  message: string
  priority: string
}

export const PIPELINE_STATUSES = [
  "planned", "generating", "generated",
  "validating", "validated", "failed",
  "compared", "selected", "rejected",
  "refactoring", "refactored",
] as const

export type PipelineStatus = typeof PIPELINE_STATUSES[number]

export const APPROACH_TYPES = [
  "direct_fix", "minimal_change", "refactored", "alternative", "conservative",
] as const

export type ApproachType = typeof APPROACH_TYPES[number]
