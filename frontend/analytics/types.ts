export type AnalyticsState = "active" | "paused" | "completed" | "failed"

export type TrendDirection = "up" | "down" | "flat" | "volatile"

export type KPIStatus = "good" | "warning" | "critical" | "unknown"

export type ForecastState = "preparing" | "ready" | "failed"

export type AnalyticsResult = "success" | "failure" | "partial" | "skipped"

export interface AnalyticsSession {
  id: string
  name: string
  state: AnalyticsState
  metricIds: string[]
  startedAt: string
  updatedAt: string
  completedAt: string | null
  metadata: Record<string, unknown>
}

export interface AnalyticsMetric {
  id: string
  name: string
  category: string
  unit: string
  value: number
  timestamp: string
  dimensions: MetricDimension[]
  source: string
}

export interface AggregatedMetric {
  id: string
  name: string
  category: string
  unit: string
  aggregation: string
  value: number
  count: number
  min: number
  max: number
  sum: number
  avg: number
  timestamp: string
  dimensions: MetricDimension[]
}

export interface MetricDimension {
  name: string
  value: string
}

export interface TrendAnalysis {
  id: string
  metricName: string
  direction: TrendDirection
  changePercent: number
  points: TrendPoint[]
  period: string
  confidence: number
  generatedAt: string
}

export interface TrendPoint {
  timestamp: string
  value: number
  label: string
}

export interface KPI {
  id: string
  name: string
  description: string
  category: string
  value: number
  target: number
  unit: string
  status: KPIStatus
  threshold: KPIThreshold
  timestamp: string
  trend: TrendDirection
}

export interface KPIThreshold {
  goodMin: number
  goodMax: number
  warningMin: number
  warningMax: number
}

export interface ExecutiveReport {
  id: string
  title: string
  period: string
  sections: ExecutiveSection[]
  generatedAt: string
  summary: string
  metadata: Record<string, unknown>
}

export interface ExecutiveSection {
  id: string
  title: string
  type: string
  content: Record<string, unknown>
  metrics: Record<string, number>
}

export interface OperationalInsight {
  id: string
  type: string
  severity: "info" | "warning" | "critical"
  message: string
  detail: string
  metricName: string
  timestamp: string
  source: string
}

export interface ForecastDataset {
  id: string
  name: string
  metricName: string
  timeSeries: TrendPoint[]
  state: ForecastState
  normalized: boolean
  parameters: Record<string, unknown>
  createdAt: string
}

export interface AnalyticsDecision {
  id: string
  sessionId: string
  policyId: string
  action: string
  result: AnalyticsResult
  reason: string
  timestamp: string
}

export interface AnalyticsPolicy {
  id: string
  name: string
  type: "aggregation_policy" | "kpi_policy" | "reporting_policy" | "forecasting_policy" | "insight_policy"
  rules: Record<string, unknown>
  enabled: boolean
  priority: number
}

export interface AnalyticsCheckpoint {
  id: string
  sessionId: string
  stage: string
  status: "pending" | "passed" | "failed" | "skipped"
  checkedAt: string
  details: string
}

export interface AnalyticsSnapshot {
  id: string
  sessionId: string
  state: AnalyticsState
  metricCount: number
  kpiCount: number
  timestamp: string
}

export interface AnalyticsMetrics {
  totalSessions: number
  activeSessions: number
  totalAggregations: number
  totalKPIs: number
  totalReports: number
  totalTrends: number
  totalInsights: number
  totalDatasets: number
}

export interface AnalyticsHealth {
  status: "healthy" | "degraded" | "unhealthy"
  aggregationFailures: number
  kpiFailures: number
  reportingFailures: number
  insightFailures: number
  recoveryReady: boolean
  lastSnapshot: string | null
}

export interface AnalyticsRequest {
  id: string
  type: string
  payload: Record<string, unknown>
  metadata: Record<string, string>
  timestamp: string
}

export interface AnalyticsResponse {
  id: string
  requestId: string
  success: boolean
  data: Record<string, unknown> | null
  errors: string[]
  timestamp: string
}

export interface AnalyticsCapabilityDefinition {
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
