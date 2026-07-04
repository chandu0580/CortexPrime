export type TaskState =
  | "CREATED"
  | "QUEUED"
  | "READY"
  | "ASSIGNED"
  | "RUNNING"
  | "WAITING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED"

export type DependencyType = "hard" | "soft" | "signal"

export type BatchStatus = "preparing" | "running" | "completed" | "partial" | "failed"

export interface ExecutionTask {
  id: string
  sessionId: string
  batchId: string | null
  name: string
  description: string
  state: TaskState
  priority: number
  workerId: string | null
  dependencies: TaskDependency[]
  checkpoints: TaskCheckpoint[]
  result: TaskResult | null
  retryCount: number
  maxRetries: number
  createdAt: string
  startedAt: string | null
  completedAt: string | null
  timeout: string
  metadata: Record<string, string>
}

export interface TaskQueue {
  id: string
  name: string
  sessionId: string
  tasks: ExecutionTask[]
  capacity: number
  createdAt: string
  updatedAt: string
}

export interface TaskBatch {
  id: string
  sessionId: string
  name: string
  description: string
  tasks: ExecutionTask[]
  status: BatchStatus
  totalTasks: number
  completedTasks: number
  failedTasks: number
  createdAt: string
  completedAt: string | null
}

export interface TaskDependency {
  id: string
  taskId: string
  dependsOnTaskId: string
  type: DependencyType
  satisfied: boolean
  details: string
}

export interface TaskPriority {
  taskId: string
  basePriority: number
  adjustedPriority: number
  factors: string[]
}

export interface TaskAssignment {
  id: string
  taskId: string
  sessionId: string
  workerId: string
  assignedAt: string
  startedAt: string | null
  completedAt: string | null
  status: "assigned" | "started" | "completed" | "failed" | "revoked"
}

export interface TaskCheckpoint {
  id: string
  taskId: string
  name: string
  description: string
  order: number
  reached: boolean
  reachedAt: string | null
  metadata: Record<string, string> | null
}

export interface TaskResult {
  taskId: string
  status: "success" | "failure" | "partial"
  output: Record<string, unknown>
  summary: string
  completedAt: string
  durationMs: number | null
  error: string | null
}

export interface TaskMetrics {
  totalTasks: number
  activeTasks: number
  queuedTasks: number
  completedTasks: number
  failedTasks: number
  cancelledTasks: number
  waitingTasks: number
  averageCompletionTimeMs: number
  totalCheckpoints: number
  totalBatches: number
  queueDepth: number
}
