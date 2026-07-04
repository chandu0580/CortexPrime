export enum RuntimeState {
  PENDING = "pending",
  PREFLIGHT = "preflight",
  LOADING = "loading",
  INITIALIZING = "initializing",
  COMPOSING = "composing",
  ACTIVATING = "activating",
  ACTIVE = "active",
  SHUTDOWN = "shutdown",
  FAILED = "failed",
  RECOVERING = "recovering",
}

export enum RuntimeStatus {
  HEALTHY = "healthy",
  DEGRADED = "degraded",
  UNHEALTHY = "unhealthy",
  UNKNOWN = "unknown",
  STARTING = "starting",
}

export enum StartupStrategy {
  SEQUENTIAL = "sequential",
  TOPOLOGICAL = "topological",
}

export enum ShutdownStrategy {
  GRACEFUL = "graceful",
  FORCED = "forced",
  ROLLING = "rolling",
}

export enum ValidationSeverity {
  CRITICAL = "critical",
  HIGH = "high",
  MEDIUM = "medium",
  LOW = "low",
  INFO = "info",
}

export interface CortexRuntimeInstance {
  id: string
  version: string
  state: RuntimeState
  status: RuntimeStatus
  startedAt: string | null
  updatedAt: string
  uptimeMs: number
}

export interface RuntimeManifest {
  id: string
  modules: RuntimeModuleRecord[]
  version: string
  createdAt: string
  updatedAt: string
}

export interface RuntimeModuleRecord {
  id: string
  name: string
  version: string
  package: string
  dependencies: string[]
  required: boolean
}

export interface RuntimeStage {
  id: string
  name: string
  order: number
  state: RuntimeState
  startedAt: string | null
  completedAt: string | null
  durationMs: number
}

export interface RuntimePipeline {
  id: string
  stages: RuntimeStage[]
  currentStage: string | null
  state: RuntimeState
  startedAt: string | null
  completedAt: string | null
}

export interface RuntimeStartupResult {
  success: boolean
  state: RuntimeState
  stagesCompleted: number
  totalStages: number
  durationMs: number
  errors: string[]
}

export interface RuntimeShutdownResult {
  success: boolean
  state: RuntimeState
  modulesDeactivated: number
  durationMs: number
  errors: string[]
}

export interface RuntimeRecovery {
  id: string
  attempt: number
  fromState: RuntimeState
  toState: RuntimeState
  strategy: StartupStrategy
  success: boolean
  errors: string[]
  timestamp: string
}

export interface RuntimeSnapshot {
  id: string
  instanceId: string
  state: RuntimeState
  stages: RuntimeStage[]
  modules: string[]
  timestamp: string
}

export interface RuntimeTransition {
  id: string
  instanceId: string
  fromState: RuntimeState
  toState: RuntimeState
  reason: string
  timestamp: string
}

export interface RuntimeValidation {
  id: string
  instanceId: string
  startupValid: boolean
  shutdownValid: boolean
  dependencyIntegrity: boolean
  moduleReadiness: boolean
  runtimeConsistent: boolean
  errors: string[]
  warnings: string[]
  timestamp: string
}

export interface RuntimeMetricsData {
  startupDurationMs: number
  shutdownDurationMs: number
  restartCount: number
  failureCount: number
  recoveryCount: number
  totalModules: number
  activeModules: number
  moduleCoverage: number
  totalTransitions: number
  uptimeMs: number
}

export interface RuntimeHealthData {
  platformReady: boolean
  startupHealthy: boolean
  shutdownHealthy: boolean
  dependencyHealthy: boolean
  recoveryReady: boolean
  currentState: RuntimeState
  currentStatus: RuntimeStatus
  lastError: string | null
  healthyModules: number
  totalModules: number
}

export interface RuntimeRequest {
  id: string
  action: "start" | "shutdown" | "restart" | "recover" | "validate"
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