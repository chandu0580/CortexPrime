import type { PlatformError } from "@/platform/contracts"

export type PipelineState =
  | "pending"
  | "building"
  | "ready"
  | "running"
  | "paused"
  | "completed"
  | "failed"
  | "cancelled"

export type StageStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "skipped"
  | "cancelled"

export interface PipelineDefinition {
  id: string
  name: string
  description: string
  version: string
  stages: string[]
  tags: string[]
  timeoutMs: number
  maxRetries: number
  createdBy: string
  createdAt: string
}

export interface PipelineStage {
  id: string
  name: string
  description: string
  pipelineId: string
  dependencies: string[]
  order: number
  timeoutMs: number
  retryCount: number
  maxRetries: number
  inputSchema: Record<string, unknown>
  outputSchema: Record<string, unknown>
  tags: string[]
}

export interface PipelineContext {
  pipelineId: string
  executionId: string
  sessionId: string
  correlationId: string
  currentStageId: string | null
  completedStageIds: string[]
  variables: Record<string, unknown>
  metadata: Record<string, string>
  startedAt: string
  updatedAt: string
}

export interface StageInput {
  stageId: string
  executionId: string
  context: PipelineContext
  payload: Record<string, unknown>
  previousStageOutput: Record<string, unknown> | null
}

export interface StageOutput {
  stageId: string
  executionId: string
  data: Record<string, unknown>
  metadata: Record<string, string>
  completedAt: string
}

export interface StageResult {
  stageId: string
  status: StageStatus
  input: StageInput
  output: StageOutput | null
  error: PlatformError | null
  startedAt: string
  completedAt: string
  durationMs: number
  retryAttempt: number
}

export interface PipelineExecution {
  id: string
  pipelineId: string
  state: PipelineState
  currentStageId: string | null
  stageResults: StageResult[]
  context: PipelineContext
  error: PlatformError | null
  startedAt: string
  updatedAt: string
  completedAt: string | null
}

export interface PipelineMetrics {
  pipelineId: string
  executionId: string
  totalStages: number
  completedStages: number
  failedStages: number
  skippedStages: number
  totalDurationMs: number
  averageStageDurationMs: number
  stageDurations: Record<string, number>
  retryCount: number
  errorCount: number
  startedAt: string
  collectedAt: string
}

export interface PipelineCheckpoint {
  id: string
  pipelineId: string
  executionId: string
  stageId: string
  state: PipelineState
  context: PipelineContext
  stageResults: StageResult[]
  savedAt: string
  expiresAt: string
  version: number
}
