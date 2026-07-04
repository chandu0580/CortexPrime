import type { Priority } from "@/types/intelligence"

export type DecisionState =
  | "draft"
  | "pending_approval"
  | "approved"
  | "rejected"
  | "needs_review"
  | "escalated"
  | "deferred"
  | "revising"

export type ApprovalLevel = "none" | "team" | "management" | "executive"

export type RouteTarget = "runtime" | "review" | "intervention" | "learning" | "mission_revision"

export type PolicyResult = "passed" | "failed" | "needs_review"

export interface DecisionAction {
  id: string
  type: string
  description: string
  assignedTo: string
  deadline: string
}

export interface DecisionPolicy {
  id: string
  name: string
  category: string
  evaluation: PolicyResult
  details: string
}

export interface DecisionApproval {
  required: boolean
  level: ApprovalLevel
  approvedBy: string | null
  approvedAt: string | null
  conditions: string[]
}

export interface DecisionEscalation {
  required: boolean
  reason: string
  targetLevel: string
  triggeredBy: string
}

export interface DecisionRoute {
  target: RouteTarget
  reason: string
  priority: Priority
}

export interface AuditEvent {
  id: string
  timestamp: string
  actor: string
  action: string
  details: string
}

export interface DecisionAudit {
  id: string
  decisionId: string
  events: AuditEvent[]
  trail: string
}

export interface DecisionOutcome {
  id: string
  sourceDecisionId: string
  sourceCategory: string
  state: DecisionState
  route: DecisionRoute
  approval: DecisionApproval
  escalation: DecisionEscalation
  actions: DecisionAction[]
  policies: DecisionPolicy[]
  summary: string
  timestamp: string
}

export interface EnterpriseDecisionResult {
  outcomes: DecisionOutcome[]
  summary: string
  stateCounts: Record<DecisionState, number>
  audit: DecisionAudit
  timestamp: string
}
