export type CognitiveStage =
  | "intake"
  | "context_build"
  | "memory_retrieval"
  | "knowledge_resolution"
  | "worker_coordination"
  | "world_state_update"
  | "validation"
  | "completion"

export type CognitiveStatus =
  | "pending"
  | "active"
  | "paused"
  | "completed"
  | "failed"
  | "rolled_back"

export type WorkerRole =
  | "analyst"
  | "researcher"
  | "planner"
  | "coordinator"

export type CoordinationStrategy =
  | "sequential"
  | "parallel"
  | "conditional"
  | "broadcast"

export type RoutingPolicy =
  | "auto"
  | "skip_on_success"
  | "retry_on_failure"
  | "terminate_on_failure"

export interface CognitiveSession {
  id: string
  requestId: string
  status: CognitiveStatus
  currentStage: CognitiveStage
  pipelineId: string
  contextId: string
  stages: CognitiveStageDef[]
  startedAt: string
  updatedAt: string
  completedAt: string | null
  error: string | null
}

export interface CognitiveStageDef {
  id: string
  name: CognitiveStage
  order: number
  status: CognitiveStatus
  startedAt: string | null
  completedAt: string | null
  durationMs: number | null
  error: string | null
  retryCount: number
}

export interface CognitiveContext {
  id: string
  sessionId: string
  request: CognitiveRequest
  memoryEntries: string[]
  knowledgeEntities: string[]
  worldStateKeys: string[]
  workerResults: WorkerResult[]
  decisions: CognitiveDecision[]
  metadata: Record<string, string>
  createdAt: string
  updatedAt: string
}

export interface CognitivePipelineDefinition {
  id: string
  name: string
  stages: CognitiveStage[]
  strategy: CoordinationStrategy
  routingPolicy: RoutingPolicy
  maxRetries: number
  enabled: boolean
}

export interface CognitivePipelineExecution {
  id: string
  pipelineId: string
  sessionId: string
  stages: CognitiveStageDef[]
  status: CognitiveStatus
  currentStageIndex: number
  startedAt: string
  completedAt: string | null
  durationMs: number | null
}

export interface WorkerAssignment {
  id: string
  sessionId: string
  workerId: string
  workerType: string
  role: WorkerRole
  status: "assigned" | "active" | "completed" | "failed" | "released"
  task: string
  assignedAt: string
  completedAt: string | null
  result: WorkerResult | null
}

export interface WorkerInvocation {
  assignmentId: string
  workerId: string
  sessionId: string
  task: string
  payload: Record<string, unknown>
  status: "pending" | "in_progress" | "completed" | "failed"
  invokedAt: string
  completedAt: string | null
}

export interface WorkerResult {
  assignmentId: string
  workerId: string
  success: boolean
  output: Record<string, unknown> | null
  error: string | null
  durationMs: number
  completedAt: string
}

export interface CognitiveDecision {
  id: string
  sessionId: string
  stage: CognitiveStage
  action: "proceed" | "skip" | "retry" | "terminate" | "rollback"
  reason: string
  route: CognitiveRoute | null
  timestamp: string
}

export interface CognitiveRoute {
  type: "forward" | "skip" | "retry" | "terminate"
  currentStage: CognitiveStage
  nextStage: CognitiveStage | null
  conditions: string[]
}

export interface CognitiveCheckpoint {
  id: string
  sessionId: string
  stage: CognitiveStage
  context: CognitiveContext | null
  snapshotId: string | null
  createdAt: string
}

export interface CognitiveSnapshot {
  id: string
  sessionId: string
  context: CognitiveContext | null
  stages: CognitiveStageDef[]
  status: CognitiveStatus
  capturedAt: string
}

export interface CognitiveTransition {
  id: string
  sessionId: string
  fromStage: CognitiveStage
  toStage: CognitiveStage
  fromStatus: CognitiveStatus
  toStatus: CognitiveStatus
  reason: string
  timestamp: string
  durationMs: number
}

export interface CognitivePolicy {
  id: string
  name: string
  description: string
  category: "availability" | "context" | "memory" | "graph" | "state" | "general"
  effect: "allow" | "deny" | "audit"
  rules: CognitivePolicyRule[]
  priority: number
  enabled: boolean
}

export interface CognitivePolicyRule {
  field: string
  operator: "exists" | "equals" | "gte" | "lte" | "in" | "not_in"
  value: unknown
  message: string
}

export interface CognitiveMetrics {
  activeSessions: number
  completedSessions: number
  failedSessions: number
  totalStagesCompleted: number
  totalStagesFailed: number
  stageDurations: Record<string, number>
  workerUtilization: Record<string, number>
  routingDecisions: number
  retries: number
  failures: number
  avgSessionDurationMs: number
  updatedAt: string
}

export interface CognitiveHealth {
  status: "healthy" | "degraded" | "unhealthy"
  activeSessions: number
  stalledSessions: number
  failedStages: number
  recoveryReady: boolean
  policyViolations: number
  lastCheckAt: string
  issues: string[]
}

export interface CognitiveRequest {
  id: string
  type: "orchestrate" | "coordinate" | "validate" | "snapshot" | "inspect"
  sessionId?: string
  pipelineId?: string
  stages?: CognitiveStage[]
  strategy?: CoordinationStrategy
  routingPolicy?: RoutingPolicy
  context?: Record<string, unknown>
  metadata?: Record<string, string>
}

export interface CognitiveResponse {
  success: boolean
  session: CognitiveSession | null
  data: Record<string, unknown> | null
  error: string | null
  durationMs: number
  timestamp: string
}

export interface CognitiveCapabilityDefinition {
  id: string
  name: string
  description: string
  capabilities: string[]
  stages: CognitiveStage[]
  strategies: CoordinationStrategy[]
  policies: RoutingPolicy[]
  version: string
}
