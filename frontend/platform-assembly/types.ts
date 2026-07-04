export enum AssemblyState {
  PENDING = "pending",
  ASSEMBLING = "assembling",
  ASSEMBLED = "assembled",
  INITIALIZING = "initializing",
  ACTIVE = "active",
  SHUTDOWN = "shutdown",
  FAILED = "failed",
}

export enum AssemblyStatus {
  HEALTHY = "healthy",
  DEGRADED = "degraded",
  UNHEALTHY = "unhealthy",
  UNKNOWN = "unknown",
}

export enum ModuleCategory {
  FOUNDATION = "foundation",
  KERNEL = "kernel",
  RUNTIME = "runtime",
  WORKER = "worker",
  CAPABILITY = "capability",
  MISSION = "mission",
  COGNITIVE = "cognitive",
  ENTERPRISE = "enterprise",
  CONNECTOR = "connector",
  INTEGRATION = "integration",
}

export interface PlatformModuleRecord {
  id: string
  name: string
  package: string
  category: ModuleCategory
  dependencies: string[]
  loaded: boolean
  initialized: boolean
}

export interface AssemblyDependency {
  moduleId: string
  dependsOn: string[]
  resolved: boolean
}

export interface AssemblyContext {
  id: string
  modules: PlatformModuleRecord[]
  state: AssemblyState
  status: AssemblyStatus
  assembledAt: string | null
  startedAt: string | null
}

export interface AssemblyHealth {
  platformReady: boolean
  moduleReady: boolean
  dependencyReady: boolean
  assemblyReady: boolean
  recoveryReady: boolean
  totalModules: number
  loadedModules: number
  activeModules: number
  lastError: string | null
}

export interface AssemblyMetrics {
  registeredModules: number
  loadedModules: number
  assemblyDurationMs: number
  dependencyCount: number
  coverage: number
  startupReady: boolean
}

export interface AssemblyRequest {
  id: string
  action: string
  timestamp: string
}

export interface AssemblyResponse {
  id: string
  success: boolean
  data: Record<string, unknown> | null
  errors: string[]
  timestamp: string
}