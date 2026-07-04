export type ConnectorState = "initialized" | "active" | "paused" | "failed" | "deactivated"

export type ConnectorType = "source" | "target" | "bidirectional"

export type SynchronizationState = "planned" | "in_progress" | "completed" | "failed"

export type EndpointType = "rest" | "graphql" | "grpc" | "websocket" | "database" | "filesystem" | "message_queue"

export type IntegrationResult = "success" | "failure" | "partial" | "skipped"

export interface IntegrationConnector {
  id: string
  name: string
  version: string
  type: ConnectorType
  state: ConnectorState
  descriptor: ConnectorDescriptor
  capabilities: ConnectorCapability[]
  endpoints: ConnectorEndpoint[]
  metadata: Record<string, unknown>
  createdAt: string
  updatedAt: string
}

export interface ConnectorDescriptor {
  id: string
  name: string
  description: string
  version: string
  vendor: string
  tags: Record<string, string>
}

export interface ConnectorRegistration {
  id: string
  connectorId: string
  registeredAt: string
  registeredBy: string
  status: "pending" | "registered" | "failed"
  details: string
}

export interface ConnectorCapability {
  id: string
  name: string
  description: string
  version: string
  supported: boolean
}

export interface ConnectorEndpoint {
  id: string
  connectorId: string
  name: string
  type: EndpointType
  url: string
  credentialRef: string | null
  config: Record<string, unknown>
  enabled: boolean
}

export interface EndpointDefinition {
  id: string
  name: string
  type: EndpointType
  baseUrl: string
  version: string
  methods: string[]
  headers: Record<string, string>
  timeout: number
  retryCount: number
}

export interface SynchronizationPlan {
  id: string
  connectorId: string
  name: string
  sourceEndpointId: string
  targetEndpointId: string
  schedule: string
  state: SynchronizationState
  jobs: SynchronizationJob[]
  createdAt: string
  updatedAt: string
  metadata: Record<string, unknown>
}

export interface SynchronizationJob {
  id: string
  planId: string
  sequence: number
  action: string
  state: SynchronizationState
  startedAt: string | null
  completedAt: string | null
  result: IntegrationResult | null
  details: string
}

export interface CredentialReference {
  id: string
  name: string
  connectorId: string
  endpointId: string | null
  type: string
  reference: string
  expiresAt: string | null
  createdAt: string
  rotatedAt: string | null
  revokedAt: string | null
  valid: boolean
}

export interface IntegrationPolicy {
  id: string
  name: string
  description: string
  type: "connector_policy" | "endpoint_policy" | "sync_policy" | "credential_policy" | "routing_policy"
  rules: IntegrationRule[]
  enabled: boolean
  priority: number
}

export interface IntegrationRule {
  id: string
  field: string
  operator: string
  value: unknown
  effect: "allow" | "deny" | "warn"
  message: string
}

export interface IntegrationDecision {
  id: string
  policyId: string
  ruleId: string
  action: string
  result: IntegrationResult
  reason: string
  timestamp: string
}

export interface IntegrationEvent {
  id: string
  source: string
  type: string
  payload: Record<string, unknown>
  timestamp: string
  correlationId: string | null
}

export interface IntegrationRoute {
  id: string
  name: string
  sourceConnectorId: string
  targetConnectorId: string
  eventTypes: string[]
  transform: string | null
  enabled: boolean
  createdAt: string
}

export interface IntegrationCheckpoint {
  id: string
  planId: string
  jobSequence: number
  label: string
  timestamp: string
  result: IntegrationResult
}

export interface IntegrationSnapshot {
  id: string
  connectorId: string
  state: ConnectorState
  endpointCount: number
  syncCount: number
  timestamp: string
}

export interface IntegrationMetrics {
  totalConnectors: number
  activeConnectors: number
  totalEndpoints: number
  totalSyncPlans: number
  totalSyncJobs: number
  totalRoutes: number
  totalCredentials: number
  totalEvents: number
}

export interface IntegrationHealth {
  status: "healthy" | "degraded" | "unhealthy"
  inactiveConnectors: number
  failedSyncs: number
  endpointFailures: number
  routingFailures: number
  credentialIssues: number
  lastSnapshot: string | null
}

export interface IntegrationRequest {
  id: string
  type: string
  payload: Record<string, unknown>
  metadata: Record<string, string>
  timestamp: string
}

export interface IntegrationResponse {
  id: string
  requestId: string
  success: boolean
  data: Record<string, unknown> | null
  errors: string[]
  timestamp: string
}

export interface IntegrationCapabilityDefinition {
  id: string
  name: string
  description: string
  version: string
  enabled: boolean
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
