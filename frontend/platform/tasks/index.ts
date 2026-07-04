import type { PlatformError } from "../contracts"

export type TaskStatus = "pending" | "queued" | "assigned" | "running" | "completed" | "failed" | "cancelled"

export type TaskDependencyType = "hard" | "soft" | "signal"

export interface TaskDefinition {
  id: string
  sessionId: string
  name: string
  payload: Record<string, unknown>
  timeout: string
  maxRetries: number
  dependencies: string[]
}

export interface TaskProgress {
  taskId: string
  status: TaskStatus
  progress: number
  workerId: string | null
  startedAt: string | null
  error: PlatformError | null
}
