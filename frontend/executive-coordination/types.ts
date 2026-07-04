export type CoordinationState = "active" | "paused" | "completed" | "failed"

export type CoordinationStrategy = "sequential" | "parallel" | "hybrid" | "dynamic"

export type DelegationPolicy = "round_robin" | "capability_based" | "load_balanced" | "priority_based"

export type SynchronizationMode = "barrier" | "dependency" | "semaphore" | "lockstep"

export type CoordinationResult = "success" | "failure" | "partial" | "deferred"

export interface CoordinationSession {
  id: string
  missionId: string
  name: string
  state: CoordinationState
  strategy: CoordinationStrategy
  stages: CoordinationStage[]
  checkpoints: CoordinationCheckpoint[]
  createdAt: string
  updatedAt: string
  completedAt: string | null
  metadata: Record<string, unknown>
}

export interface CoordinationPlan {
  id: string
  sessionId: string
  name: string
  stages: CoordinationStage[]
  totalTasks: number
  completedTasks: number
  strategy: CoordinationStrategy
  createdAt: string
  updatedAt: string
}

export interface CoordinationStage {
  id: string
  name: string
  sequence: number
  tasks: CoordinationTask[]
  state: CoordinationState
  startedAt: string | null
  completedAt: string | null
}

export interface CoordinationTask {
  id: string
  name: string
  stageId: string
  workerId: string | null
  dependencies: string[]
  state: CoordinationState
  priority: number
  estimatedDuration: number
  startedAt: string | null
  completedAt: string | null
  result: CoordinationResult | null
  metadata: Record<string, unknown>
}

export interface WorkerCandidate {
  workerId: string
  name: string
  capabilities: string[]
  load: number
  score: number
  available: boolean
  lastHeartbeat: string | null
}

export interface WorkerSelection {
  id: string
  sessionId: string
  taskId: string
  workerId: string
  score: number
  reason: string
  selectedAt: string
}

export interface WorkerDelegation {
  id: string
  sessionId: string
  taskId: string
  workerId: string
  policy: DelegationPolicy
  status: "active" | "reassigned" | "revoked" | "completed"
  delegatedAt: string
  reassignedAt: string | null
  revokedAt: string | null
  completedAt: string | null
}

export interface CoordinationDecision {
  id: string
  sessionId: string
  type: "execute" | "retry" | "skip" | "escalate" | "abort"
  reason: string
  timestamp: string
  decidedBy: string
}

export interface CoordinationRoute {
  id: string
  sessionId: string
  source: string
  target: string
  action: string
  priority: number
}

export interface SynchronizationBarrier {
  id: string
  sessionId: string
  name: string
  mode: SynchronizationMode
  requiredWorkers: string[]
  arrivedWorkers: string[]
  state: "waiting" | "released" | "timed_out"
  createdAt: string
  releasedAt: string | null
}

export interface CoordinationCheckpoint {
  id: string
  sessionId: string
  stage: string
  status: "pending" | "passed" | "failed" | "skipped"
  checkedAt: string
  details: string
}

export interface CoordinationConflict {
  id: string
  sessionId: string
  type: "resource" | "dependency" | "priority" | "state"
  description: string
  involvedWorkers: string[]
  involvedTasks: string[]
  detectedAt: string
  resolved: boolean
}

export interface ConflictResolution {
  id: string
  conflictId: string
  resolution: string
  action: string
  resolvedBy: string
  resolvedAt: string
}

export interface CoordinationPolicy {
  id: string
  name: string
  type: "delegation_policy" | "routing_policy" | "sync_policy" | "worker_availability_policy" | "execution_ordering_policy"
  rules: Record<string, unknown>
  enabled: boolean
  priority: number
}

export interface CoordinationMetrics {
  totalSessions: number
  activeSessions: number
  totalPlans: number
  totalDelegations: number
  totalSynchronizations: number
  totalConflicts: number
  totalWorkerSelections: number
  totalDecisions: number
}

export interface CoordinationHealth {
  status: "healthy" | "degraded" | "unhealthy"
  failedDelegations: number
  syncFailures: number
  routingFailures: number
  coordinationFailures: number
  recoveryReady: boolean
  lastSnapshot: string | null
}

export interface CoordinationSnapshot {
  id: string
  sessionId: string
  state: CoordinationState
  stageCount: number
  taskCount: number
  timestamp: string
}

export interface CoordinationTransition {
  id: string
  sessionId: string
  fromState: CoordinationState
  toState: CoordinationState
  timestamp: string
  reason: string
}

export interface CoordinationRequest {
  id: string
  type: string
  payload: Record<string, unknown>
  metadata: Record<string, string>
  timestamp: string
}

export interface CoordinationResponse {
  id: string
  requestId: string
  success: boolean
  data: Record<string, unknown> | null
  errors: string[]
  timestamp: string
}

export interface ExecutiveCoordinationCapabilityDefinition {
  id: string
  name: string
  description: string
  version: string
  enabled: boolean
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
