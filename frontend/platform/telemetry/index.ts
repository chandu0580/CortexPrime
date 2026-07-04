export type MetricType = "counter" | "gauge" | "histogram" | "event"

export interface TelemetryEvent {
  name: string
  type: MetricType
  value: number
  tags: Record<string, string>
  timestamp: string
}

export interface TelemetryQuery {
  metricName: string
  fromTimestamp: string
  toTimestamp: string
  aggregation: "sum" | "avg" | "min" | "max" | "count"
  groupBy: string[]
}

export interface TelemetrySnapshot {
  totalEvents: number
  totalMetrics: number
  totalErrors: number
  earliestEvent: string | null
  latestEvent: string | null
}
