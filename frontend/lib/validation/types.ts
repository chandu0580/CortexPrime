export type ScenarioId = "deploy-service" | "production-incident" | "security-review" | "release-management" | "mission-recovery"

export type ServiceName =
  | "GitHub" | "Docker" | "Kubernetes" | "Prometheus" | "Grafana"
  | "Jira" | "Slack" | "Security Agent" | "Compliance Agent"
  | "Knowledge" | "Governance" | "Planner" | "Execution"
  | "Rollback" | "Replay"

export type ValidationDimension =
  | "mission_lifecycle" | "ai_decisions" | "agent_coordination"
  | "knowledge_retrieval" | "learning_updates" | "governance"
  | "execution" | "connector_execution" | "artifacts"
  | "replay" | "timeline" | "metrics"

export type ValidationStatus = "pass" | "fail" | "skip" | "error"

export interface ValidationCheckpoint {
  id: string
  dimension: ValidationDimension
  description: string
  required: boolean
  status: ValidationStatus
  durationMs: number
  detail: string
  evidence?: string
}

export interface ScenarioService {
  name: ServiceName
  actions: string[]
  durationMs: number
  status: ValidationStatus
}

export interface ScenarioResult {
  id: ScenarioId
  title: string
  goal: string
  services: ScenarioService[]
  checkpoints: ValidationCheckpoint[]
  startedAt: string
  completedAt: string
  totalDurationMs: number
  passCount: number
  failCount: number
  skipCount: number
  overallStatus: ValidationStatus
  score: number
}

export interface ReportSummary {
  totalScenarios: number
  passed: number
  failed: number
  totalCheckpoints: number
  passedCheckpoints: number
  failedCheckpoints: number
  skippedCheckpoints: number
  overallScore: number
  totalDurationMs: number
}

export interface CoverageItem {
  dimension: ValidationDimension
  tested: number
  passed: number
  failed: number
  coveragePercent: number
}

export interface PerfMetric {
  scenarioId: ScenarioId
  checkpointsTotal: number
  checkpointsPassed: number
  durationMs: number
  score: number
}

export interface FailureItem {
  scenarioId: ScenarioId
  scenarioTitle: string
  checkpointId: string
  dimension: ValidationDimension
  description: string
  detail: string
  severity: "high" | "medium" | "low"
}

export interface MissionSuccessItem {
  scenarioId: ScenarioId
  title: string
  goal: string
  score: number
  status: ValidationStatus
  servicesUsed: number
  servicesPassed: number
}

export interface ProductionReadinessReport {
  generatedAt: string
  overallScore: number
  readinessLevel: "critical" | "low" | "medium" | "high" | "production_ready"
  summary: ReportSummary
  coverage: CoverageItem[]
  performance: PerfMetric[]
  failures: FailureItem[]
  missionSuccess: MissionSuccessItem[]
  knownGaps: string[]
  riskAssessment: { category: string; level: "low" | "medium" | "high"; description: string }[]
  recommendations: string[]
}

export interface ValidationSuiteConfig {
  scenarios: ScenarioId[]
  timeoutMs: number
  reportDir?: string
}
