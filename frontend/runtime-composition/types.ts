export enum RuntimeCompositionState {
  PENDING = "pending",
  INITIALIZING = "initializing",
  ACTIVE = "active",
  PAUSED = "paused",
  SHUTDOWN = "shutdown",
  FAILED = "failed",
}

export enum RuntimeCompositionStatus {
  HEALTHY = "healthy",
  DEGRADED = "degraded",
  UNHEALTHY = "unhealthy",
  UNKNOWN = "unknown",
  STARTING = "starting",
}

export enum RuntimeModuleType {
  CORE = "core",
  SCHEDULER = "scheduler",
  RESOURCE = "resource",
  WORKER = "worker",
  CAPABILITY = "capability",
  EVENT = "event",
  TELEMETRY = "telemetry",
  LIFECYCLE = "lifecycle",
  FAILURE = "failure",
  RETRY = "retry",
}

export enum RuntimeCompositionStrategy {
  SEQUENTIAL = "sequential",
  TOPOLOGICAL = "topological",
  PARALLEL = "parallel",
}

export enum ValidationSeverity {
  CRITICAL = "critical",
  HIGH = "high",
  MEDIUM = "medium",
  LOW = "low",
  INFO = "info",
}

export interface RuntimeModule {
  id: string
  name: string
  version: string
  type: RuntimeModuleType
  dependencies: string[]
  state: RuntimeCompositionState
  startedAt: string | null
  completedAt: string | null
}

export interface RuntimeComposition {
  id: string
  name: string
  version: string
  modules: RuntimeModule[]
  state: RuntimeCompositionState
  status: RuntimeCompositionStatus
  createdAt: string
  updatedAt: string
}

export interface RuntimeContext {
  id: string
  compositionId: string
  data: Record<string, unknown>
  version: number
  createdAt: string
  updatedAt: string
}

export interface RuntimeDependency {
  moduleId: string
  dependsOn: string[]
  resolved: boolean
}

export interface RuntimeSnapshot {
  id: string
  compositionId: string
  state: RuntimeCompositionState
  modules: RuntimeModule[]
  context: RuntimeContext
  timestamp: string
}

export interface RuntimeTransition {
  id: string
  compositionId: string
  fromState: RuntimeCompositionState
  toState: RuntimeCompositionState
  reason: string
  timestamp: string
}

export interface RuntimeExecutionOrder {
  id: string
  moduleIds: string[]
  strategy: RuntimeCompositionStrategy
  valid: boolean
}

export interface RuntimeValidation {
  id: string
  compositionId: string
  moduleReadiness: boolean
  dependencyIntegrity: boolean
  executionOrderValid: boolean
  lifecycleValid: boolean
  runtimeHealth: boolean
  errors: string[]
  warnings: string[]
  timestamp: string
}

export interface RuntimeMetricsData {
  moduleCount: number
  activeModules: number
  startupDurationMs: number
  shutdownDurationMs: number
  restartCount: number
  executionCoverage: number
  dependencyCount: number
  totalTransitions: number
}

export interface RuntimeHealthData {
  runtimeReady: boolean
  dependencyHealth: boolean
  lifecycleHealth: boolean
  recoveryReady: boolean
  currentState: RuntimeCompositionState
  lastError: string | null
  healthyModules: number
  totalModules: number
}

export interface RuntimeRequest {
  id: string
  action: "compose" | "initialize" | "shutdown" | "restart" | "validate"
  payload: Record<string, unknown>
  timestamp: string
}

export interface RuntimeResponse {
  id: string
  requestId: string
  success: boolean
  data: Record<string, unknown> | null
  errors: string[]
  timestamp: string
}

export interface RuntimeCapabilityDefinition {
  id: string
  name: string
  description: string
  version: string
  enabled: boolean
}
