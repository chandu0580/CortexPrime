export enum TestStatus {
  PASSED = "passed",
  FAILED = "failed",
  SKIPPED = "skipped",
  WARNING = "warning",
  ERROR = "error",
}

export enum ValidationSeverity {
  CRITICAL = "critical",
  HIGH = "high",
  MEDIUM = "medium",
  LOW = "low",
  INFO = "info",
}

export enum CoverageLevel {
  FULL = "full",
  PARTIAL = "partial",
  MINIMAL = "minimal",
  NONE = "none",
}

export enum ReportFormat {
  JSON = "json",
  SUMMARY = "summary",
  DETAILED = "detailed",
}

export enum ConnectorCompliance {
  FULLY_COMPLIANT = "fully_compliant",
  PARTIALLY_COMPLIANT = "partially_compliant",
  NON_COMPLIANT = "non_compliant",
  UNKNOWN = "unknown",
}

export interface ConnectorTestSuite {
  id: string
  connectorName: string
  testCases: ConnectorTestCase[]
  startedAt: string
  completedAt: string | null
  status: TestStatus
  summary: ConnectorSummary
}

export interface ConnectorTestCase {
  id: string
  suiteId: string
  name: string
  description: string
  category: "contract" | "lifecycle" | "capability" | "permission" | "health" | "metrics" | "event"
  status: TestStatus
  severity: ValidationSeverity
  errors: string[]
  warnings: string[]
  durationMs: number
}

export interface ConnectorTestResult {
  id: string
  suiteId: string
  connectorId: string
  connectorName: string
  passed: number
  failed: number
  skipped: number
  warnings: number
  total: number
  compliance: ConnectorCompliance
  complianceScore: number
  startedAt: string
  completedAt: string
}

export interface ConnectorValidationReport {
  id: string
  connectorName: string
  contract: ConnectorContractResult
  lifecycle: ConnectorLifecycleResult
  capability: ConnectorCapabilityResult
  permission: ConnectorPermissionResult
  health: ConnectorHealthResult
  metrics: ConnectorMetricResult
  event: ConnectorEventResult
  summary: ConnectorSummary
  coverage: ConnectorCoverage
  issues: ConnectorIssue[]
  recommendations: ConnectorRecommendation[]
  compliance: ConnectorCompliance
  complianceScore: number
  generatedAt: string
}

export interface ConnectorContractResult {
  implementsAbstractConnector: boolean
  hasRequiredMethods: boolean
  hasRequiredExports: boolean
  hasCapabilityRegistration: boolean
  methodsPresent: string[]
  methodsMissing: string[]
  status: TestStatus
  errors: string[]
}

export interface ConnectorCapabilityResult {
  totalCapabilities: number
  expectedCapabilities: number
  namesValid: boolean
  duplicatesFound: boolean
  stageMappingValid: boolean
  capabilities: string[]
  status: TestStatus
  errors: string[]
}

export interface ConnectorLifecycleResult {
  initializeSupported: boolean
  shutdownSupported: boolean
  activateSupported: boolean
  pauseSupported: boolean
  resumeSupported: boolean
  deactivateSupported: boolean
  validTransitions: boolean
  status: TestStatus
  errors: string[]
}

export interface ConnectorPermissionResult {
  evaluatorCount: number
  expectedEvaluators: number
  evaluators: string[]
  policyAvailable: boolean
  validationConsistent: boolean
  status: TestStatus
  errors: string[]
}

export interface ConnectorHealthResult {
  healthReporting: boolean
  metricsReporting: boolean
  heartbeatSupported: boolean
  statusReporting: boolean
  status: TestStatus
  errors: string[]
}

export interface ConnectorMetricResult {
  metricsRegistered: boolean
  aggregationSupported: boolean
  reportingSupported: boolean
  metricCount: number
  status: TestStatus
  errors: string[]
}

export interface ConnectorEventResult {
  eventNamingValid: boolean
  eventPublishingSupported: boolean
  eventCategoryValid: boolean
  payloadConsistent: boolean
  eventsPublished: string[]
  status: TestStatus
  errors: string[]
}

export interface ConnectorSummary {
  totalTests: number
  passed: number
  failed: number
  skipped: number
  warnings: number
  durationMs: number
}

export interface ConnectorCoverage {
  overall: CoverageLevel
  contract: CoverageLevel
  lifecycle: CoverageLevel
  capability: CoverageLevel
  permission: CoverageLevel
  health: CoverageLevel
  metrics: CoverageLevel
  event: CoverageLevel
}

export interface ConnectorIssue {
  id: string
  category: string
  severity: ValidationSeverity
  message: string
  recommendation: string
}

export interface ConnectorRecommendation {
  id: string
  category: string
  priority: "high" | "medium" | "low"
  message: string
}

export interface ConnectorHarnessMetrics {
  totalConnectorsValidated: number
  totalTestsRun: number
  totalPassed: number
  totalFailed: number
  totalWarnings: number
  averageComplianceScore: number
  fullyCompliant: number
  partiallyCompliant: number
  nonCompliant: number
  lastRunAt: string | null
}

export interface ConnectorHarnessHealth {
  status: "healthy" | "degraded" | "unhealthy" | "unknown"
  lastValidationAt: string | null
  totalConnectors: number
  validationErrors: number
  details: Record<string, unknown>
}

export interface ConnectorHarnessRequest {
  id: string
  action: string
  connectorName: string | null
  timestamp: string
}

export interface ConnectorHarnessResponse {
  id: string
  requestId: string
  success: boolean
  data: Record<string, unknown> | null
  errors: string[]
  timestamp: string
}