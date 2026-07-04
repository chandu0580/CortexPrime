export type PipelineStage =
  | "user_intent"
  | "mission_session"
  | "mission_intelligence"
  | "enterprise_reasoning"
  | "enterprise_decision"
  | "mission_orchestrator"
  | "execution_readiness"
  | "runtime"

export type MissionState =
  | "created"
  | "initializing"
  | "intaking"
  | "analyzing"
  | "reasoning"
  | "deciding"
  | "orchestrating"
  | "validating"
  | "ready_for_runtime"
  | "completed"
  | "failed"
  | "cancelled"

export type KernelState =
  | "initializing"
  | "running"
  | "degraded"
  | "stopped"
  | "error"

export type EngineStatus = "registered" | "active" | "error" | "disabled"

export interface EngineDescriptor {
  id: string
  name: string
  version: string
  pipelineStage: PipelineStage
  description: string
  inputTypes: string[]
  outputTypes: string[]
}

export interface EngineRegistration {
  descriptor: EngineDescriptor
  status: EngineStatus
  registeredAt: string
  lastHeartbeat: string | null
  invocations: number
}

export interface EngineInvocation {
  id: string
  engineId: string
  sessionId: string
  stage: PipelineStage
  input: Record<string, unknown>
  output: Record<string, unknown>
  startedAt: string
  completedAt: string | null
  duration: number | null
  status: "running" | "completed" | "failed"
  error: string | null
}

export interface MissionSession {
  id: string
  externalId: string
  state: MissionState
  pipelineStage: PipelineStage
  context: KernelContext
  correlationId: string
  createdAt: string
  updatedAt: string
  completedAt: string | null
  invocations: EngineInvocation[]
  telemetry: TelemetryEvent[]
}

export interface KernelContext {
  missionId: string
  sessionId: string
  correlationId: string
  userIntent: string | null
  data: Record<string, unknown>
  errors: string[]
  warnings: string[]
  propagatedFrom: string | null
  propagatedAt: string | null
}

export interface PipelineTransition {
  id: string
  sessionId: string
  fromStage: PipelineStage
  toStage: PipelineStage
  timestamp: string
  triggeredBy: string
}

export interface CorrelationContext {
  id: string
  sessionId: string
  parentCorrelationId: string | null
  engineIds: string[]
  startedAt: string
  hops: string[]
}

export interface KernelMetadata {
  version: string
  kernelState: KernelState
  startedAt: string
  uptimeMs: number
  registeredEngineCount: number
  activeSessionCount: number
  totalInvocations: number
  totalErrors: number
}

export interface KernelLifecycle {
  id: string
  event: string
  description: string
  timestamp: string
  sessionId: string | null
  metadata: Record<string, string> | null
}

export interface PipelineExecution {
  id: string
  sessionId: string
  stages: PipelineStage[]
  currentStage: PipelineStage
  transitions: PipelineTransition[]
  startedAt: string
  completedAt: string | null
  status: "running" | "completed" | "failed" | "cancelled"
  error: string | null
}

export interface TelemetryEvent {
  id: string
  sessionId: string
  type: string
  name: string
  details: string
  timestamp: string
  durationMs: number | null
  metadata: Record<string, string> | null
}
