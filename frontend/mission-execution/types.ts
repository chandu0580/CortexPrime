export type ExecutionState =
  | "pending"
  | "planning"
  | "distributing"
  | "executing"
  | "paused"
  | "completed"
  | "failed"
  | "rolled_back"

export type ExecutionStage =
  | "decomposition"
  | "planning"
  | "distribution"
  | "dependency_check"
  | "validation"
  | "execution"
  | "monitoring"
  | "completion"

export type DistributionStrategy =
  | "balanced"
  | "sequential"
  | "parallel"
  | "round_robin"
  | "capacity_first"

export type AssignmentPolicy =
  | "single"
  | "multi"
  | "dedicated"
  | "shared"

export type ValidationResult =
  | "pass"
  | "fail"
  | "warning"
  | "skip"

export interface MissionExecutionSession {
  id: string
  missionId: string
  orchestrationSessionId: string | null
  status: ExecutionState
  currentStage: ExecutionStage
  planId: string | null
  dependencyGraphId: string
  startedAt: string
  updatedAt: string
  completedAt: string | null
  error: string | null
}

export interface ExecutionPlan {
  id: string
  sessionId: string
  phases: ExecutionPhase[]
  totalTasks: number
  distributionStrategy: DistributionStrategy
  assignmentPolicy: AssignmentPolicy
  maxConcurrency: number
  validated: boolean
  finalized: boolean
  createdAt: string
  updatedAt: string
}

export interface ExecutionPhase {
  id: string
  name: string
  order: number
  stages: ExecutionStageDef[]
  status: ExecutionState
  startedAt: string | null
  completedAt: string | null
}

export interface ExecutionStageDef {
  id: string
  name: ExecutionStage
  order: number
  status: ExecutionState
  startedAt: string | null
  completedAt: string | null
  durationMs: number | null
  error: string | null
}

export interface ExecutionBatch {
  id: string
  sessionId: string
  phaseId: string
  taskGroups: ExecutionTaskGroup[]
  strategy: DistributionStrategy
  status: ExecutionState
  createdAt: string
  completedAt: string | null
}

export interface ExecutionTaskGroup {
  id: string
  batchId: string
  name: string
  tasks: DistributedTask[]
  parallel: boolean
  status: ExecutionState
  createdAt: string
  completedAt: string | null
}

export interface DistributedTask {
  id: string
  groupId: string
  name: string
  description: string
  workerType: string
  requiredCapabilities: string[]
  payload: Record<string, unknown>
  priority: number
  dependencies: string[]
  status: "pending" | "assigned" | "completed" | "failed"
  assignedWorkerId: string | null
  createdAt: string
  completedAt: string | null
}

export interface WorkerAssignment {
  id: string
  taskId: string
  sessionId: string
  workerId: string
  workerType: string
  status: "pending" | "assigned" | "active" | "completed" | "failed" | "released"
  assignedAt: string
  completedAt: string | null
}

export interface ExecutionDependency {
  id: string
  sessionId: string
  sourceTaskId: string
  targetTaskId: string
  type: "hard" | "soft" | "ordering"
  resolved: boolean
  createdAt: string
  resolvedAt: string | null
}

export interface ExecutionCheckpoint {
  id: string
  sessionId: string
  stage: ExecutionStage
  planId: string | null
  dependenciesResolved: boolean
  assignmentsComplete: boolean
  planValidated: boolean
  policiesSatisfied: boolean
  ready: boolean
  checkedAt: string
}

export interface ExecutionProgress {
  totalTasks: number
  completedTasks: number
  failedTasks: number
  inProgressTasks: number
  pendingTasks: number
  percentComplete: number
  estimatedRemainingMs: number
}

export interface ExecutionPolicy {
  id: string
  name: string
  description: string
  category: "concurrency" | "assignment" | "ordering" | "approval" | "constraint" | "general"
  effect: "allow" | "deny" | "audit"
  rules: ExecutionPolicyRule[]
  priority: number
  enabled: boolean
}

export interface ExecutionPolicyRule {
  field: string
  operator: "exists" | "equals" | "gte" | "lte" | "in" | "not_in"
  value: unknown
  message: string
}

export interface ExecutionDecision {
  id: string
  sessionId: string
  stage: ExecutionStage
  action: "proceed" | "retry" | "rollback" | "pause" | "terminate"
  reason: string
  timestamp: string
}

export interface ExecutionSnapshot {
  id: string
  sessionId: string
  plan: ExecutionPlan | null
  phases: ExecutionPhase[]
  status: ExecutionState
  progress: ExecutionProgress | null
  capturedAt: string
}

export interface ExecutionTransition {
  id: string
  sessionId: string
  fromStage: ExecutionStage
  toStage: ExecutionStage
  fromState: ExecutionState
  toState: ExecutionState
  reason: string
  timestamp: string
}

export interface ExecutionMetrics {
  activeSessions: number
  completedSessions: number
  failedSessions: number
  totalTasksDistributed: number
  totalTasksCompleted: number
  totalTasksFailed: number
  assignmentUtilization: Record<string, number>
  dependencyCount: number
  validationPasses: number
  validationFailures: number
  avgSessionDurationMs: number
  updatedAt: string
}

export interface ExecutionHealth {
  status: "healthy" | "degraded" | "unhealthy"
  activeSessions: number
  stalledExecutions: number
  failedAssignments: number
  dependencyFailures: number
  policyViolations: number
  recoveryReady: boolean
  lastCheckAt: string
  issues: string[]
}

export interface ExecutionRequest {
  id: string
  type: "execute" | "build_plan" | "distribute" | "validate" | "snapshot" | "inspect"
  missionId: string
  sessionId?: string
  planId?: string
  stages?: ExecutionStage[]
  strategy?: DistributionStrategy
  assignmentPolicy?: AssignmentPolicy
  context?: Record<string, unknown>
  metadata?: Record<string, string>
}

export interface ExecutionResponse {
  success: boolean
  session: MissionExecutionSession | null
  plan: ExecutionPlan | null
  data: Record<string, unknown> | null
  error: string | null
  durationMs: number
  timestamp: string
}

export interface ExecutionCapabilityDefinition {
  id: string
  name: string
  description: string
  capabilities: string[]
  stages: ExecutionStage[]
  strategies: DistributionStrategy[]
  policies: AssignmentPolicy[]
  version: string
}
