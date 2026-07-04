import type { MetricSeries, MetricSample, MetricType } from "./types"
import { generateId } from "./shared"

const metrics = new Map<string, MetricSeries>()

export const MetricsRegistry = {
  async registerMetric(
    name: string,
    type: MetricType,
    unit: string = "",
    description: string = "",
    labels: Record<string, string> = {},
    interval: number = 60000,
  ): Promise<MetricSeries> {
    if (metrics.has(name)) throw new Error(`Metric already registered: ${name}`)
    const id = generateId("metric")
    const series: MetricSeries = {
      id,
      name,
      type,
      unit,
      description,
      labels,
      samples: [],
      interval,
    }
    metrics.set(name, series)
    return series
  },

  async recordMetric(name: string, value: number, labels: Record<string, string> = {}): Promise<MetricSample> {
    const series = metrics.get(name)
    if (!series) throw new Error(`Metric not registered: ${name}`)
    const sample: MetricSample = {
      timestamp: new Date().toISOString(),
      value,
      labels,
    }
    series.samples.push(sample)
    metrics.set(name, series)
    return sample
  },

  async aggregateMetrics(name: string, windowMs: number = 60000): Promise<{ min: number; max: number; avg: number; sum: number; count: number } | null> {
    const series = metrics.get(name)
    if (!series) return null
    const cutoff = Date.now() - windowMs
    const recent = series.samples.filter((s) => new Date(s.timestamp).getTime() >= cutoff)
    if (recent.length === 0) return null
    const values = recent.map((s) => s.value)
    return {
      min: Math.min(...values),
      max: Math.max(...values),
      avg: values.reduce((a, b) => a + b, 0) / values.length,
      sum: values.reduce((a, b) => a + b, 0),
      count: values.length,
    }
  },

  async queryMetrics(filter?: { name?: string; type?: MetricType }): Promise<MetricSeries[]> {
    let result = Array.from(metrics.values())
    if (filter?.name) result = result.filter((m) => m.name === filter.name)
    if (filter?.type) result = result.filter((m) => m.type === filter.type)
    return result
  },

  async getMetric(name: string): Promise<MetricSeries | null> {
    return metrics.get(name) ?? null
  },
}
