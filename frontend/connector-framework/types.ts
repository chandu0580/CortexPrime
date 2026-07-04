export type ConnectorState = "initialized" | "active" | "paused" | "failed" | "deactivated"

export type ConnectorStatus = "healthy" | "degraded" | "unhealthy" | "unknown"

export type ConnectorType = "source" | "target" | "bidirectional" | "transform"

export type ConnectorPermissionLevel = "read" | "write" | "admin" | "custom"

export type ConnectorValidationResult = "passed" | "failed" | "warning" | "error"

export interface ConnectorDefinition {
  id: string
  name: string
  version: string
  type: ConnectorType
  identity: ConnectorIdentity
  metadata: ConnectorMetadata
  capabilities: ConnectorCapability[]
  endpoints: ConnectorEndpoint[]
  permissions: ConnectorPermission[]
  state: ConnectorState
  status: ConnectorStatus
  createdAt: string
  updatedAt: string
}

export interface ConnectorIdentity {
  id: string
  name: string
  vendor: string
  version: string
  description: string
  tags: Record<string, string>
}

export interface ConnectorMetadata {
  displayName: string
  description: string
  category: string
  icon: string
  documentationUrl: string
  supportUrl: string
  tags: string[]
}

export interface ConnectorSession {
  id: string
  connectorId: string
  state: ConnectorState
  startedAt: string
  updatedAt: string
  completedAt: string | null
  metadata: Record<string, unknown>
}

export interface ConnectorCapability {
  id: string
  name: string
  description: string
  version: string
  supported: boolean
  config: Record<string, unknown>
}

export interface ConnectorConfiguration {
  id: string
  connectorId: string
  key: string
  value: unknown
  sensitive: boolean
  updatedAt: string
}

export interface ConnectorEndpoint {
  id: string
  connectorId: string
  name: string
  url: string
  methods: string[]
  headers: Record<string, string>
  timeout: number
  retryCount: number
  enabled: boolean
}

export interface ConnectorPermission {
  id: string
  connectorId: string
  resource: string
  level: ConnectorPermissionLevel
  granted: boolean
}

export interface ConnectorHealth {
  status: ConnectorStatus
  state: ConnectorState
  uptimeMs: number
  lastHeartbeat: string | null
  lastError: string | null
  details: Record<string, unknown>
}

export interface ConnectorMetric {
  id: string
  connectorId: string
  name: string
  value: number
  unit: string
  timestamp: string
  labels: Record<string, string>
}

export interface ConnectorPolicy {
  id: string
  name: string
  type: "connector_policy" | "capability_policy" | "permission_policy" | "lifecycle_policy" | "configuration_policy"
  rules: Record<string, unknown>
  enabled: boolean
  priority: number
}

export interface ConnectorValidation {
  id: string
  connectorId: string
  type: string
  result: ConnectorValidationResult
  errors: string[]
  warnings: string[]
  details: Record<string, unknown>
  timestamp: string
}

export interface ConnectorSnapshot {
  id: string
  connectorId: string
  state: ConnectorState
  status: ConnectorStatus
  capabilityCount: number
  endpointCount: number
  timestamp: string
}

export interface ConnectorLifecycle {
  id: string
  connectorId: string
  fromState: ConnectorState
  toState: ConnectorState
  reason: string
  timestamp: string
}

export interface ConnectorEvent {
  id: string
  connectorId: string
  type: string
  data: Record<string, unknown>
  timestamp: string
}

export interface ConnectorRequest {
  id: string
  connectorId: string
  action: string
  payload: Record<string, unknown>
  timestamp: string
}

export interface ConnectorResponse {
  id: string
  requestId: string
  success: boolean
  data: Record<string, unknown> | null
  errors: string[]
  timestamp: string
}

export interface ConnectorCapabilityDefinition {
  id: string
  name: string
  description: string
  version: string
  enabled: boolean
}

export interface ValveMetrics {
  totalConnectors: number
  activeConnectors: number
  totalSessions: number
  totalCapabilities: number
  totalLifecycleEvents: number
  totalValidations: number
  totalEndpoints: number
  totalPermissions: number
}

export interface ValveHealth {
  status: "healthy" | "degraded" | "unhealthy"
  inactiveConnectors: number
  validationFailures: number
  lifecycleFailures: number
  capabilityFailures: number
  lastSnapshot: string | null
}

export interface ValidationResult {
  id: string
  type: string
  passed: boolean
  errors: string[]
  warnings: string[]
  details: Record<string, unknown>
}

export interface HealthSnapshot {
  timestamp: string
  component: string
  status: "healthy" | "degraded" | "unhealthy"
  metrics: Record<string, number>
  details: string
}

export interface ConnectorRegistration {
  connectorId: string
  definition: ConnectorDefinition
  registeredAt: string
  lastSeenAt: string
}
