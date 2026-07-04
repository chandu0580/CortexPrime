export type PlanningState =
  | "draft"
  | "planning"
  | "analyzing"
  | "optimizing"
  | "validating"
  | "finalized"
  | "paused"
  | "failed"
  | "cancelled"

export type PlanningPriority =
  | "critical"
  | "high"
  | "medium"
  | "low"
  | "backlog"

export type PlanningStrategy =
  | "waterfall"
  | "iterative"
  | "parallel"
  | "incremental"
  | "opportunistic"

export type PlanningPolicy =
  | "strict_priority"
  | "balanced"
  | "resource_first"
  | "deadline_first"
  | "portfolio_aware"

export type PlanningValidationResult =
  | "pass"
  | "fail"
  | "warning"
  | "skip"

export interface PlanningSession {
  id: string
  missionId: string
  status: PlanningState
  planId: string | null
  strategy: PlanningStrategy
  policy: PlanningPolicy
  startedAt: string
  updatedAt: string
  completedAt: string | null
  error: string | null
}

export interface MissionPlan {
  id: string
  sessionId: string
  missionId: string
  name: string
  description: string
  phases: PlanningPhase[]
  priority: PlanningPriority
  strategy: PlanningStrategy
  estimatedDurationMs: number
  totalTasks: number
  validated: boolean
  finalized: boolean
  createdAt: string
  updatedAt: string
}

export interface PlanningPhase {
  id: string
  name: string
  order: number
  description: string
  tasks: PlanningTask[]
  status: PlanningState
  startedAt: string | null
  completedAt: string | null
  estimatedDurationMs: number
}

export interface PlanningTask {
  id: string
  phaseId: string
  name: string
  description: string
  workerType: string
  requiredCapabilities: string[]
  priority: number
  estimatedEffortMs: number
  dependencies: string[]
  status: PlanningState
  assignedWorkerId: string | null
  createdAt: string
}

export interface PlanningDependency {
  id: string
  sessionId: string
  sourceTaskId: string
  targetTaskId: string
  type: "hard" | "soft" | "ordering" | "resource"
  resolved: boolean
  createdAt: string
  resolvedAt: string | null
}

export interface PlanningPriorityScore {
  id: string
  missionId: string
  sessionId: string
  level: PlanningPriority
  score: number
  urgency: number
  impact: number
  effort: number
  calculatedAt: string
}

export interface PlanningTimeline {
  id: string
  sessionId: string
  planId: string
  phases: PlanningPhaseTimeline[]
  totalDurationMs: number
  milestones: PlanningMilestone[]
  estimatedStartAt: string
  estimatedEndAt: string
  createdAt: string
}

export interface PlanningPhaseTimeline {
  phaseId: string
  phaseName: string
  order: number
  startOffsetMs: number
  durationMs: number
  parallel: boolean
}

export interface PlanningMilestone {
  id: string
  name: string
  description: string
  phaseId: string
  offsetMs: number
  criteria: string[]
}

export interface PlanningResource {
  id: string
  sessionId: string
  workerType: string
  requiredCount: number
  availableCount: number
  estimatedLoad: number
  reserved: boolean
  estimatedAt: string
}

export interface PlanningConstraint {
  id: string
  sessionId: string
  type: "time" | "resource" | "dependency" | "policy" | "capacity"
  description: string
  severity: "blocking" | "warning" | "info"
  active: boolean
}

export interface PlanningRisk {
  id: string
  sessionId: string
  description: string
  probability: number
  impact: number
  mitigation: string
  status: "identified" | "mitigated" | "accepted" | "realized"
}

export interface PlanningCheckpoint {
  id: string
  sessionId: string
  stage: string
  dependenciesResolved: boolean
  resourcesAvailable: boolean
  timelineValid: boolean
  priorityDefined: boolean
  planComplete: boolean
  ready: boolean
  checkedAt: string
}

export interface PlanningDecision {
  id: string
  sessionId: string
  stage: string
  action: "proceed" | "revise" | "replan" | "escalate" | "terminate"
  reason: string
  timestamp: string
}

export interface PlanningSnapshot {
  id: string
  sessionId: string
  plan: MissionPlan | null
  status: PlanningState
  capturedAt: string
}

export interface PlanningTransition {
  id: string
  sessionId: string
  fromState: PlanningState
  toState: PlanningState
  reason: string
  timestamp: string
}

export interface PlanningPortfolio {
  id: string
  name: string
  description: string
  missionIds: string[]
  plans: MissionPlan[]
  totalEffortMs: number
  priority: PlanningPriority
  conflicts: PortfolioConflict[]
  optimized: boolean
  createdAt: string
}

export interface PortfolioConflict {
  id: string
  type: "resource" | "timeline" | "dependency" | "priority"
  description: string
  sourceMissionId: string
  targetMissionId: string
  severity: "high" | "medium" | "low"
}

export interface PlanningMetrics {
  activeSessions: number
  completedSessions: number
  failedSessions: number
  plansCreated: number
  plansFinalized: number
  totalDependencies: number
  resolvedDependencies: number
  resourceEstimates: number
  portfolioCount: number
  avgPlanningDurationMs: number
  updatedAt: string
}

export interface PlanningHealth {
  status: "healthy" | "degraded" | "unhealthy"
  activeSessions: number
  planningFailures: number
  dependencyIssues: number
  resourceConflicts: number
  optimizationFailures: number
  recoveryReady: boolean
  lastCheckAt: string
  issues: string[]
}

export interface PlanningRequest {
  id: string
  type: "create_plan" | "optimize" | "validate" | "estimate" | "timeline" | "portfolio" | "inspect"
  missionId: string
  sessionId?: string
  planId?: string
  name?: string
  description?: string
  strategy?: PlanningStrategy
  policy?: PlanningPolicy
  priority?: PlanningPriority
  context?: Record<string, unknown>
  metadata?: Record<string, string>
}

export interface PlanningResponse {
  success: boolean
  session: PlanningSession | null
  plan: MissionPlan | null
  data: Record<string, unknown> | null
  error: string | null
  durationMs: number
  timestamp: string
}

export interface PlanningCapabilityDefinition {
  id: string
  name: string
  description: string
  capabilities: string[]
  strategies: PlanningStrategy[]
  policies: PlanningPolicy[]
  version: string
}
