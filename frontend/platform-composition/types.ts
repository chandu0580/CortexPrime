export enum CompositionState {
  INITIALIZED = "initialized",
  ACTIVE = "active",
  PAUSED = "paused",
  SHUTDOWN = "shutdown",
  FAILED = "failed",
}

export enum CompositionStatus {
  HEALTHY = "healthy",
  DEGRADED = "degraded",
  UNHEALTHY = "unhealthy",
  UNKNOWN = "unknown",
}

export enum DependencyType {
  HARD = "hard",
  SOFT = "soft",
  OPTIONAL = "optional",
}

export enum CompositionStrategy {
  SEQUENTIAL = "sequential",
  PARALLEL = "parallel",
  TOPOLOGICAL = "topological",
}

export enum ValidationSeverity {
  CRITICAL = "critical",
  HIGH = "high",
  MEDIUM = "medium",
  LOW = "low",
  INFO = "info",
}

export interface PlatformComposition {
  id: string
  name: string
  version: string
  nodes: CompositionNode[]
  edges: CompositionEdge[]
  state: CompositionState
  status: CompositionStatus
  createdAt: string
  updatedAt: string
}

export interface CompositionNode {
  id: string
  moduleId: string
  moduleName: string
  moduleVersion: string
  category: string
  dependencies: string[]
  initialized: boolean
  active: boolean
  startedAt: string | null
}

export interface CompositionEdge {
  id: string
  sourceId: string
  targetId: string
  type: DependencyType
  required: boolean
}

export interface CompositionDependency {
  moduleId: string
  dependsOn: string[]
  type: DependencyType
  resolved: boolean
}

export interface CompositionContext {
  id: string
  compositionId: string
  state: Record<string, unknown>
  version: number
  createdAt: string
  updatedAt: string
}

export interface CompositionSnapshot {
  id: string
  compositionId: string
  state: CompositionState
  nodes: CompositionNode[]
  context: CompositionContext
  timestamp: string
}

export interface CompositionTransition {
  id: string
  compositionId: string
  fromState: CompositionState
  toState: CompositionState
  reason: string
  timestamp: string
}

export interface CompositionValidation {
  id: string
  compositionId: string
  dependenciesValid: boolean
  lifecycleValid: boolean
  contextValid: boolean
  healthValid: boolean
  metricsValid: boolean
  errors: string[]
  warnings: string[]
  timestamp: string
}

export interface CompositionMetricsData {
  moduleCount: number
  activeModules: number
  dependencyCount: number
  startupDurationMs: number
  shutdownDurationMs: number
  compositionCoverage: number
  totalTransitions: number
  failedTransitions: number
}

export interface CompositionHealthData {
  platformReady: boolean
  dependenciesHealthy: boolean
  lifecycleHealthy: boolean
  recoveryReady: boolean
  activeNodeCount: number
  totalNodeCount: number
  lastTransition: string | null
  lastError: string | null
}

export interface CompositionRequest {
  id: string
  action: "compose" | "initialize" | "shutdown" | "validate" | "snapshot"
  payload: Record<string, unknown>
  timestamp: string
}

export interface CompositionResponse {
  id: string
  requestId: string
  success: boolean
  data: Record<string, unknown> | null
  errors: string[]
  timestamp: string
}

export interface CompositionCapabilityDefinition {
  id: string
  name: string
  description: string
  version: string
  enabled: boolean
}