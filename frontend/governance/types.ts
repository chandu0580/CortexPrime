export type GovernanceState = "active" | "paused" | "completed" | "failed"

export type PolicyResult = "pass" | "fail" | "review" | "error"

export type ComplianceState = "compliant" | "non_compliant" | "pending" | "unknown"

export type ApprovalState = "pending" | "approved" | "rejected" | "revoked"

export type RiskLevel = "low" | "medium" | "high" | "critical"

export interface GovernanceSession {
  id: string
  missionId: string
  state: GovernanceState
  policyIds: string[]
  checkpoints: GovernanceCheckpoint[]
  createdAt: string
  updatedAt: string
  completedAt: string | null
  metadata: Record<string, unknown>
}

export interface GovernancePolicy {
  id: string
  name: string
  description: string
  category: string
  version: string
  enabled: boolean
  priority: number
  rules: PolicyRule[]
  tags: Record<string, string>
  createdAt: string
  updatedAt: string
}

export interface PolicyRule {
  id: string
  field: string
  operator: string
  value: unknown
  effect: "allow" | "deny" | "review"
  message: string
}

export interface PolicyEvaluation {
  id: string
  policyId: string
  ruleId: string
  sessionId: string
  result: PolicyResult
  details: string
  timestamp: string
  metadata: Record<string, unknown>
}

export interface ComplianceResult {
  id: string
  sessionId: string
  policyId: string
  state: ComplianceState
  violations: string[]
  warnings: string[]
  checkedAt: string
  details: Record<string, unknown>
}

export interface ApprovalRequest {
  id: string
  sessionId: string
  action: string
  requestedBy: string
  reason: string
  state: ApprovalState
  approver: string | null
  decidedAt: string | null
  createdAt: string
  metadata: Record<string, unknown>
}

export interface ApprovalDecision {
  id: string
  requestId: string
  approver: string
  state: ApprovalState
  reason: string
  timestamp: string
}

export interface RiskAssessment {
  id: string
  sessionId: string
  level: RiskLevel
  score: number
  factors: string[]
  mitigations: string[]
  assessedAt: string
  details: Record<string, unknown>
}

export interface GovernanceDecision {
  id: string
  sessionId: string
  action: string
  result: "allow" | "deny" | "review" | "override"
  reason: string
  decidedBy: string
  timestamp: string
  overrides: string | null
}

export interface GovernanceCheckpoint {
  id: string
  sessionId: string
  stage: string
  status: "pending" | "passed" | "failed" | "skipped"
  checkedAt: string
  details: string
}

export interface GovernanceAudit {
  id: string
  sessionId: string
  action: string
  actor: string
  target: string
  detail: string
  timestamp: string
  metadata: Record<string, unknown>
}

export interface GovernanceViolation {
  id: string
  sessionId: string
  policyId: string
  ruleId: string
  severity: RiskLevel
  message: string
  timestamp: string
  resolved: boolean
  resolvedAt: string | null
}

export interface GovernanceException {
  id: string
  sessionId: string
  policyId: string
  ruleId: string
  reason: string
  grantedBy: string
  expiresAt: string
  createdAt: string
}

export interface GovernanceSnapshot {
  id: string
  sessionId: string
  state: GovernanceState
  policyCount: number
  violationCount: number
  approvalCount: number
  timestamp: string
}

export interface GovernanceMetrics {
  totalSessions: number
  activeSessions: number
  totalEvaluations: number
  totalApprovals: number
  totalViolations: number
  totalDecisions: number
  totalComplianceChecks: number
  totalRiskAssessments: number
}

export interface GovernanceHealth {
  status: "healthy" | "degraded" | "unhealthy"
  failedEvaluations: number
  policyViolations: number
  approvalFailures: number
  complianceFailures: number
  recoveryReady: boolean
  lastSnapshot: string | null
}

export interface GovernanceRequest {
  id: string
  type: string
  payload: Record<string, unknown>
  metadata: Record<string, string>
  timestamp: string
}

export interface GovernanceResponse {
  id: string
  requestId: string
  success: boolean
  data: Record<string, unknown> | null
  errors: string[]
  timestamp: string
}

export interface ValidationResult {
  id: string
  type: string
  passed: boolean
  errors: string[]
  warnings: string[]
  details: Record<string, unknown>
}

export interface HealthSnapshot {
  timestamp: string
  component: string
  status: "healthy" | "degraded" | "unhealthy"
  metrics: Record<string, number>
  details: string
}

export interface GovernanceCapabilityDefinition {
  id: string
  name: string
  description: string
  version: string
  enabled: boolean
}
