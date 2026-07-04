import type { MissionSession } from "@/cortex-kernel/types"

export type ExecutionState =
  | "CREATED"
  | "ASSIGNED"
  | "READY"
  | "RUNNING"
  | "PAUSED"
  | "RESUMED"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED"

export type WorkerStatus = "idle" | "busy" | "error" | "offline"

export type WorkerCapability = "browser" | "voice" | "computer_use" | "research" | "integration" | "automation" | "custom"

export type TaskState = "pending" | "assigned" | "running" | "completed" | "failed" | "cancelled" | "retrying"

export interface ExecutionWorker {
  id: string
  name: string
  version: string
  capability: WorkerCapability
  status: WorkerStatus
  currentSessionId: string | null
  currentTaskId: string | null
  registeredAt: string
  lastHeartbeat: string | null
  totalTasksCompleted: number
  totalTasksFailed: number
  metadata: Record<string, string>
}

export interface WorkerRegistration {
  worker: ExecutionWorker
  registeredAt: string
  healthy: boolean
  lastCheckedAt: string
}

export interface WorkerAssignment {
  id: string
  sessionId: string
  workerId: string
  taskId: string
  assignedAt: string
  completedAt: string | null
  status: "active" | "completed" | "failed" | "revoked"
}

export interface ExecutionTask {
  id: string
  sessionId: string
  name: string
  description: string
  capability: WorkerCapability
  state: TaskState
  assignedWorkerId: string | null
  checkpoints: ExecutionCheckpoint[]
  retryCount: number
  maxRetries: number
  createdAt: string
  startedAt: string | null
  completedAt: string | null
  failureRecord: FailureRecord | null
}

export interface ExecutionCheckpoint {
  id: string
  taskId: string
  name: string
  description: string
  order: number
  reached: boolean
  reachedAt: string | null
  metadata: Record<string, string> | null
}

export interface ExecutionHeartbeat {
  id: string
  workerId: string
  sessionId: string
  taskId: string
  timestamp: string
  status: "alive" | "degraded" | "stuck"
  message: string
}

export interface RetryPolicy {
  id: string
  taskId: string
  maxRetries: number
  retryCount: number
  backoffMs: number
  backoffMultiplier: number
  maxBackoffMs: number
  retryableErrors: string[]
  lastRetryAt: string | null
  nextRetryAt: string | null
}

export interface FailureRecord {
  id: string
  taskId: string
  sessionId: string
  workerId: string | null
  error: string
  errorType: string
  occurredAt: string
  recovered: boolean
  recoveredAt: string | null
  retryAttempted: boolean
  retryCount: number
}

export interface RuntimeEvent {
  id: string
  sessionId: string
  type: string
  name: string
  details: string
  timestamp: string
  metadata: Record<string, string> | null
}

export interface RuntimeMetrics {
  activeSessions: number
  totalSessions: number
  activeWorkers: number
  idleWorkers: number
  totalWorkers: number
  tasksCompleted: number
  tasksFailed: number
  tasksRunning: number
  totalHeartbeats: number
  totalEvents: number
  uptimeMs: number
}

export interface ExecutionSession {
  id: string
  kernelSessionId: string
  kernelSession: MissionSession | null
  state: ExecutionState
  workerId: string | null
  worker: ExecutionWorker | null
  tasks: ExecutionTask[]
  checkpoints: ExecutionCheckpoint[]
  assignment: WorkerAssignment | null
  heartbeats: ExecutionHeartbeat[]
  retryPolicies: RetryPolicy[]
  failures: FailureRecord[]
  events: RuntimeEvent[]
  startedAt: string
  updatedAt: string
  completedAt: string | null
}
