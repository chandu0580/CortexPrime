export enum BootstrapState {
  PENDING = "pending",
  INITIALIZING = "initializing",
  BOOTSTRAPPING = "bootstrapping",
  ACTIVE = "active",
  SHUTDOWN = "shutdown",
  FAILED = "failed",
}

export enum BootstrapStatus {
  HEALTHY = "healthy",
  DEGRADED = "degraded",
  UNHEALTHY = "unhealthy",
  UNKNOWN = "unknown",
  STARTING = "starting",
}

export enum BootstrapStageType {
  PRECHECK = "precheck",
  LOAD = "load",
  INITIALIZE = "initialize",
  CONFIGURE = "configure",
  ACTIVATE = "activate",
  VERIFY = "verify",
}

export enum BootstrapStrategy {
  SEQUENTIAL = "sequential",
  TOPOLOGICAL = "topological",
}

export enum ValidationSeverity {
  CRITICAL = "critical",
  HIGH = "high",
  MEDIUM = "medium",
  LOW = "low",
  INFO = "info",
}

export interface BootstrapModule {
  id: string
  name: string
  version: string
  stage: BootstrapStageType
  dependencies: string[]
  status: BootstrapState
  startedAt: string | null
  completedAt: string | null
}

export interface BootstrapStage {
  id: string
  type: BootstrapStageType
  label: string
  modules: string[]
  status: BootstrapState
  startedAt: string | null
  completedAt: string | null
}

export interface BootstrapSequenceData {
  id: string
  stages: BootstrapStage[]
  strategy: BootstrapStrategy
  status: BootstrapState
  startedAt: string | null
  completedAt: string | null
}

export interface BootstrapDependency {
  moduleId: string
  dependsOn: string[]
  resolved: boolean
}

export interface BootstrapContext {
  id: string
  sessionId: string
  data: Record<string, unknown>
  version: number
  createdAt: string
  updatedAt: string
}

export interface BootstrapSnapshot {
  id: string
  sessionId: string
  state: BootstrapState
  modules: BootstrapModule[]
  context: BootstrapContext
  timestamp: string
}

export interface BootstrapTransition {
  id: string
  sessionId: string
  fromState: BootstrapState
  toState: BootstrapState
  reason: string
  timestamp: string
}

export interface BootstrapValidation {
  id: string
  sessionId: string
  startupOrderValid: boolean
  dependenciesValid: boolean
  lifecycleValid: boolean
  readinessValid: boolean
  healthValid: boolean
  errors: string[]
  warnings: string[]
  timestamp: string
}

export interface BootstrapMetricsData {
  startupDurationMs: number
  totalStages: number
  completedStages: number
  failedStages: number
  restartCount: number
  startupCoverage: number
  totalModules: number
  activeModules: number
}

export interface BootstrapHealthData {
  startupReady: boolean
  dependencyReady: boolean
  restartReady: boolean
  recoveryReady: boolean
  currentState: BootstrapState
  currentStage: string | null
  lastError: string | null
  healthyModules: number
  totalModules: number
}

export interface BootstrapRequest {
  id: string
  action: "bootstrap" | BootstrapState.SHUTDOWN | "restart" | "validate" | "snapshot"
  payload: Record<string, unknown>
  timestamp: string
}

export interface BootstrapResponse {
  id: string
  requestId: string
  success: boolean
  data: Record<string, unknown> | null
  errors: string[]
  timestamp: string
}

export interface BootstrapCapabilityDefinition {
  id: string
  name: string
  description: string
  version: string
  enabled: boolean
}