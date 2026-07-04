import type { PlatformError } from "../contracts"

export type ExecutionMode = "synchronous" | "asynchronous" | "background" | "scheduled"

export type ExecutionStatus = "pending" | "running" | "paused" | "completed" | "failed" | "cancelled"

export interface ExecutionPlan {
  id: string
  sessionId: string
  stages: string[]
  mode: ExecutionMode
  timeout: string
  createdAt: string
}

export interface ExecutionStageResult {
  stageName: string
  status: ExecutionStatus
  output: Record<string, unknown> | null
  error: PlatformError | null
  startedAt: string
  completedAt: string | null
  durationMs: number | null
}
