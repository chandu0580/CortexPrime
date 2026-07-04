export enum ApplicationState {
  PENDING = "pending",
  INITIALIZING = "initializing",
  STARTING = "starting",
  ACTIVE = "active",
  STOPPING = "stopping",
  SHUTDOWN = "shutdown",
  FAILED = "failed",
}

export enum ApplicationEnvironmentType {
  DEVELOPMENT = "development",
  TESTING = "testing",
  STAGING = "staging",
  PRODUCTION = "production",
  AIR_GAPPED = "air_gapped",
}

export enum ApplicationStatus {
  HEALTHY = "healthy",
  DEGRADED = "degraded",
  UNHEALTHY = "unhealthy",
  UNKNOWN = "unknown",
}

export enum FeatureFlagState {
  ENABLED = "enabled",
  DISABLED = "disabled",
}

export interface ApplicationConfiguration {
  id: string
  environment: ApplicationEnvironmentType
  version: string
  features: Record<string, FeatureFlagState>
  settings: Record<string, unknown>
  loadedAt: string
}

export interface ApplicationEnvironment {
  type: ApplicationEnvironmentType
  name: string
  deploymentMode: string
  runtimeProfile: string
  features: string[]
}

export interface ApplicationModule {
  id: string
  name: string
  package: string
  dependencies: string[]
  registered: boolean
}

export interface ApplicationService {
  id: string
  name: string
  instance: unknown
  singleton: boolean
}

export interface ApplicationDependency {
  moduleId: string
  dependsOn: string[]
  resolved: boolean
}

export interface ApplicationFeature {
  id: string
  name: string
  state: FeatureFlagState
  description: string
}

export interface ApplicationStartupResult {
  success: boolean
  state: ApplicationState
  durationMs: number
  stagesCompleted: string[]
  errors: string[]
}

export interface ApplicationShutdownResult {
  success: boolean
  state: ApplicationState
  durationMs: number
  errors: string[]
}

export interface ApplicationDiagnostic {
  platformStatus: string
  runtimeStatus: string
  workerStatus: string
  connectorStatus: string
  missionStatus: string
  health: Record<string, unknown>
  metrics: Record<string, unknown>
  validation: Record<string, unknown>
}

export interface ApplicationMetrics {
  startupDurationMs: number
  shutdownDurationMs: number
  modulesRegistered: number
  servicesRegistered: number
  featuresEnabled: number
  uptimeMs: number
}

export interface ApplicationHealth {
  state: ApplicationState
  status: ApplicationStatus
  modulesHealthy: number
  totalModules: number
  lastError: string | null
  uptimeMs: number
}

export interface ApplicationContext {
  id: string
  state: ApplicationState
  config: ApplicationConfiguration
  environment: ApplicationEnvironment
  startedAt: string | null
}

export interface ApplicationSnapshot {
  id: string
  context: ApplicationContext
  modules: ApplicationModule[]
  services: ApplicationService[]
  timestamp: string
}

export interface ApplicationCapability {
  id: string
  name: string
  description: string
  enabled: boolean
}