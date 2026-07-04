export enum ValidationState {
  PENDING = "pending",
  RUNNING = "running",
  COMPLETED = "completed",
  FAILED = "failed",
}

export enum ValidationSeverity {
  CRITICAL = "critical",
  HIGH = "high",
  MEDIUM = "medium",
  LOW = "low",
  INFO = "info",
}

export enum ValidationStatus {
  PASSED = "passed",
  FAILED = "failed",
  SKIPPED = "skipped",
  WARNING = "warning",
}

export enum SmokeTestStatus {
  PASSED = "passed",
  FAILED = "failed",
  SKIPPED = "skipped",
}

export interface ValidationSession {
  id: string
  state: ValidationState
  startedAt: string | null
  completedAt: string | null
  summary: ValidationSummary
}

export interface SmokeTest {
  id: string
  name: string
  description: string
  status: SmokeTestStatus
  durationMs: number
  error: string | null
}

export interface SmokeTestResult {
  total: number
  passed: number
  failed: number
  skipped: number
  durationMs: number
  tests: SmokeTest[]
}

export interface ValidationResult {
  id: string
  name: string
  status: ValidationStatus
  severity: ValidationSeverity
  errors: string[]
  durationMs: number
}

export interface ValidationIssue {
  id: string
  resultId: string
  severity: ValidationSeverity
  message: string
  recommendation: string
}

export interface ValidationWarning {
  id: string
  resultId: string
  message: string
}

export interface ValidationSummary {
  total: number
  passed: number
  failed: number
  skipped: number
  warnings: number
  durationMs: number
}

export interface DependencyValidation {
  totalDependencies: number
  resolved: number
  unresolved: number
  cyclesFound: number
  valid: boolean
  errors: string[]
}

export interface LifecycleValidation {
  moduleCount: number
  validTransitions: number
  invalidTransitions: number
  valid: boolean
  errors: string[]
}

export interface RuntimeValidationData {
  runtimeReady: boolean
  compositionValid: boolean
  startupSequenceValid: boolean
  restartSupported: boolean
  recoverySupported: boolean
  valid: boolean
  errors: string[]
}

export interface HealthValidation {
  platformHealthy: boolean
  runtimeHealthy: boolean
  dependencyHealthy: boolean
  modulesHealthy: number
  totalModules: number
  valid: boolean
  errors: string[]
}

export interface MetricsValidation {
  metricsCollected: boolean
  coverageValid: boolean
  startupDurationValid: boolean
  shutdownDurationValid: boolean
  valid: boolean
  errors: string[]
}

export interface ValidationReport {
  id: string
  sessionId: string
  summary: ValidationSummary
  smokeTests: SmokeTestResult
  dependency: DependencyValidation
  lifecycle: LifecycleValidation
  runtime: RuntimeValidationData
  health: HealthValidation
  metrics: MetricsValidation
  issues: ValidationIssue[]
  warnings: ValidationWarning[]
  recommendations: string[]
  overallScore: number
  platformReady: boolean
  generatedAt: string
}

export interface ValidationMetrics {
  totalSessions: number
  totalTests: number
  totalPassed: number
  totalFailed: number
  lastRunDurationMs: number
  averageScore: number
}

export interface ValidationHealth {
  healthy: boolean
  lastSessionState: ValidationState
  lastError: string | null
  totalIssues: number
}