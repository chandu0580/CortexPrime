export type TraceState = "active" | "paused" | "completed" | "failed"

export type SpanState = "started" | "completed" | "failed"

export type MetricType = "counter" | "gauge" | "histogram" | "summary"

export type AuditSeverity = "critical" | "high" | "medium" | "low" | "info"

export type ReplayState = "recording" | "paused" | "completed" | "failed"

export interface Trace {
  id: string
  traceId: string
  name: string
  service: string
  state: TraceState
  startedAt: string
  endedAt: string | null
  spanCount: number
  tags: Record<string, string>
  attributes: Record<string, unknown>
}

export interface Span {
  id: string
  traceId: string
  parentSpanId: string | null
  name: string
  state: SpanState
  kind: string
  startedAt: string
  endedAt: string | null
  durationMs: number | null
  service: string
  operation: string
  tags: Record<string, string>
  attributes: Record<string, unknown>
  logs: SpanLog[]
  status: SpanStatus | null
}

export interface SpanLog {
  timestamp: string
  message: string
  attributes: Record<string, unknown>
}

export interface SpanStatus {
  code: number
  message: string | null
}

export interface TraceContext {
  traceId: string
  parentSpanId: string | null
  spanId: string
  sampled: boolean
  baggage: Record<string, string>
}

export interface AuditRecord {
  id: string
  eventId: string
  action: string
  actor: string
  target: string
  severity: AuditSeverity
  source: string
  timestamp: string
  details: string
  metadata: Record<string, unknown>
}

export interface AuditEvent {
  id: string
  auditId: string
  type: string
  timestamp: string
  data: Record<string, unknown>
  source: string
}

export interface MetricSeries {
  id: string
  name: string
  type: MetricType
  unit: string
  description: string
  labels: Record<string, string>
  samples: MetricSample[]
  interval: number
}

export interface MetricSample {
  timestamp: string
  value: number
  labels: Record<string, string>
}

export interface ReplaySession {
  id: string
  traceId: string
  name: string
  state: ReplayState
  frames: ReplayFrame[]
  checkpoints: ReplayCheckpoint[]
  createdAt: string
  metadata: Record<string, unknown>
}

export interface ReplayFrame {
  id: string
  sessionId: string
  sequence: number
  timestamp: string
  type: string
  data: Record<string, unknown>
  durationMs: number | null
}

export interface ReplayCheckpoint {
  id: string
  sessionId: string
  frameSequence: number
  label: string
  timestamp: string
}

export interface CorrelationRecord {
  id: string
  traceId: string
  sourceType: string
  sourceId: string
  targetType: string
  targetId: string
  relationship: string
  confidence: number
  metadata: Record<string, unknown>
}

export interface DiagnosticResult {
  id: string
  traceId: string
  type: string
  severity: string
  message: string
  details: Record<string, unknown>
  timestamp: string
  source: string
}

export interface HealthSnapshot {
  timestamp: string
  component: string
  status: "healthy" | "degraded" | "unhealthy"
  metrics: Record<string, number>
  details: string
}

export interface ValidationResult {
  id: string
  type: string
  passed: boolean
  errors: string[]
  warnings: string[]
  details: Record<string, unknown>
}

export interface ObservabilityPolicy {
  id: string
  name: string
  type: "audit_retention" | "trace_policy" | "replay_policy" | "metrics_policy" | "diagnostic_policy"
  rules: Record<string, unknown>
  enabled: boolean
  priority: number
}

export interface ObservabilityDecision {
  id: string
  policyId: string
  action: string
  reason: string
  timestamp: string
}

export interface ObservabilityMetrics {
  totalTraces: number
  activeTraces: number
  totalSpans: number
  failedSpans: number
  totalAudits: number
  totalReplays: number
  totalDiagnostics: number
  totalCorrelations: number
}

export interface ObservabilityHealth {
  status: "healthy" | "degraded" | "unhealthy"
  droppedTraces: number
  failedSpans: number
  replayFailures: number
  metricFailures: number
  auditFailures: number
  lastSnapshot: string | null
}

export interface ObservabilityRequest {
  id: string
  type: string
  payload: Record<string, unknown>
  metadata: Record<string, string>
  timestamp: string
}

export interface ObservabilityResponse {
  id: string
  requestId: string
  success: boolean
  data: Record<string, unknown> | null
  errors: string[]
  timestamp: string
}

export interface ObservabilityCapabilityDefinition {
  id: string
  name: string
  description: string
  version: string
  enabled: boolean
}
