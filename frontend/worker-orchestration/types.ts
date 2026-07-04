export type WorkerExecutionState =
  | "pending"
  | "ready"
  | "executing"
  | "paused"
  | "completed"
  | "failed"
  | "rolled_back"

export type WorkerLifecycleState =
  | "registered"
  | "starting"
  | "running"
  | "pausing"
  | "paused"
  | "resuming"
  | "stopping"
  | "stopped"
  | "restarting"
  | "failed"

export type SynchronizationStrategy =
  | "barrier"
  | "phased"
  | "lockstep"
  | "independent"

export type AssignmentStrategy =
  | "round_robin"
  | "least_loaded"
  | "capability_match"
  | "dedicated"

export type WorkerValidationResult =
  | "pass"
  | "fail"
  | "warning"
  | "skip"

export interface WorkerSession {
  id: string
  orchestrationId: string
  missionId: string
  status: WorkerExecutionState
  workers: string[]
  currentGroupId: string | null
  startedAt: string
  updatedAt: string
  completedAt: string | null
  error: string | null
}

export interface WorkerExecution {
  id: string
  sessionId: string
  workerId: string
  workerType: string
  taskId: string
  status: WorkerExecutionState
  lifecycleState: WorkerLifecycleState
  startedAt: string
  updatedAt: string
  completedAt: string | null
  error: string | null
}

export interface WorkerAssignment {
  id: string
  sessionId: string
  workerId: string
  workerType: string
  taskId: string
  task: string
  capabilities: string[]
  strategy: AssignmentStrategy
  status: "pending" | "assigned" | "active" | "completed" | "failed" | "released"
  assignedAt: string
  completedAt: string | null
}

export interface WorkerGroup {
  id: string
  sessionId: string
  name: string
  workerIds: string[]
  strategy: SynchronizationStrategy
  status: WorkerExecutionState
  barrierId: string | null
  createdAt: string
  completedAt: string | null
}

export interface WorkerSynchronization {
  id: string
  sessionId: string
  groupId: string
  type: SynchronizationStrategy
  status: "pending" | "syncing" | "synced" | "failed"
  participantCount: number
  readyCount: number
  createdAt: string
  completedAt: string | null
}

export interface WorkerBarrier {
  id: string
  sessionId: string
  name: string
  participantIds: string[]
  arrivedIds: string[]
  released: boolean
  createdAt: string
  releasedAt: string | null
}

export interface WorkerDependency {
  id: string
  sessionId: string
  sourceWorkerId: string
  targetWorkerId: string
  type: "hard" | "soft" | "ordering"
  resolved: boolean
  createdAt: string
  resolvedAt: string | null
}

export interface WorkerCheckpoint {
  id: string
  sessionId: string
  workerId: string
  stage: string
  ready: boolean
  dependenciesResolved: boolean
  assigned: boolean
  validated: boolean
  checkedAt: string
}

export interface WorkerPolicy {
  id: string
  name: string
  description: string
  category: "concurrency" | "assignment" | "synchronization" | "recovery" | "ordering" | "general"
  effect: "allow" | "deny" | "audit"
  rules: WorkerPolicyRule[]
  priority: number
  enabled: boolean
}

export interface WorkerPolicyRule {
  field: string
  operator: "exists" | "equals" | "gte" | "lte" | "in" | "not_in"
  value: unknown
  message: string
}

export interface WorkerValidation {
  id: string
  sessionId: string
  workerId: string
  available: boolean
  capabilitiesCompatible: boolean
  synchronizationReady: boolean
  lifecycleValid: boolean
  consistent: boolean
  validatedAt: string
}

export interface WorkerDecision {
  id: string
  sessionId: string
  workerId: string
  action: "proceed" | "retry" | "reassign" | "recover" | "terminate"
  reason: string
  timestamp: string
}

export interface WorkerTransition {
  id: string
  sessionId: string
  workerId: string
  fromState: WorkerLifecycleState
  toState: WorkerLifecycleState
  reason: string
  timestamp: string
}

export interface WorkerSnapshot {
  id: string
  sessionId: string
  executions: WorkerExecution[]
  assignments: WorkerAssignment[]
  groups: WorkerGroup[]
  status: WorkerExecutionState
  capturedAt: string
}

export interface WorkerRecovery {
  id: string
  sessionId: string
  workerId: string
  failureType: string
  error: string
  retryCount: number
  maxRetries: number
  recovered: boolean
  strategy: "retry" | "restart" | "reassign" | "rollback"
  createdAt: string
  recoveredAt: string | null
}

export interface WorkerMetrics {
  activeSessions: number
  completedSessions: number
  failedSessions: number
  activeWorkers: number
  completedWorkers: number
  failedWorkers: number
  synchronizationCount: number
  assignmentUtilization: Record<string, number>
  recoveries: number
  avgExecutionDurationMs: number
  updatedAt: string
}

export interface WorkerHealth {
  status: "healthy" | "degraded" | "unhealthy"
  activeSessions: number
  workerFailures: number
  stalledWorkers: number
  unhealthyWorkers: number
  synchronizationFailures: number
  recoveryReady: boolean
  lastCheckAt: string
  issues: string[]
}

export interface WorkerRequest {
  id: string
  type: "orchestrate" | "assign" | "synchronize" | "validate" | "recover" | "inspect"
  missionId: string
  sessionId?: string
  workerIds?: string[]
  workerType?: string
  capabilities?: string[]
  task?: string
  strategy?: SynchronizationStrategy
  assignmentStrategy?: AssignmentStrategy
  context?: Record<string, unknown>
  metadata?: Record<string, string>
}

export interface WorkerResponse {
  success: boolean
  session: WorkerSession | null
  data: Record<string, unknown> | null
  error: string | null
  durationMs: number
  timestamp: string
}

export interface WorkerCapabilityDefinition {
  id: string
  name: string
  description: string
  capabilities: string[]
  strategies: SynchronizationStrategy[]
  assignmentStrategies: AssignmentStrategy[]
  version: string
}
