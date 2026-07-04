import type { AnalyticsMetric, AggregatedMetric, MetricDimension } from "./types"
import { generateId } from "./shared"

const aggregations = new Map<string, AggregatedMetric>()

export const MetricAggregationEngine = {
  async aggregateMetrics(metrics: AnalyticsMetric[]): Promise<AggregatedMetric[]> {
    const grouped = new Map<string, AnalyticsMetric[]>()

    for (const metric of metrics) {
      const key = `${metric.name}:${metric.unit}`
      const existing = grouped.get(key) ?? []
      existing.push(metric)
      grouped.set(key, existing)
    }

    const results: AggregatedMetric[] = []

    for (const [key, group] of grouped) {
      const [name, unit] = key.split(":")
      const values = group.map((m) => m.value)
      const sum = values.reduce((a, b) => a + b, 0)
      const count = values.length
      const min = Math.min(...values)
      const max = Math.max(...values)
      const avg = sum / count

      const aggregated: AggregatedMetric = {
        id: generateId("agg"),
        name,
        category: group[0].category,
        unit,
        aggregation: "group",
        value: avg,
        count,
        min,
        max,
        sum,
        avg,
        timestamp: new Date().toISOString(),
        dimensions: MetricAggregationEngine.mergeDimensions(group.map((m) => m.dimensions)),
      }
      aggregations.set(aggregated.id, aggregated)
      results.push(aggregated)
    }

    return results
  },

  mergeDimensions(dimensionsList: MetricDimension[][]): MetricDimension[] {
    const seen = new Set<string>()
    const result: MetricDimension[] = []
    for (const dims of dimensionsList) {
      for (const dim of dims) {
        const key = `${dim.name}:${dim.value}`
        if (!seen.has(key)) {
          seen.add(key)
          result.push(dim)
        }
      }
    }
    return result
  },

  async aggregateByCategory(metrics: AnalyticsMetric[]): Promise<AggregatedMetric[]> {
    const grouped = new Map<string, AnalyticsMetric[]>()
    for (const metric of metrics) {
      const existing = grouped.get(metric.category) ?? []
      existing.push(metric)
      grouped.set(metric.category, existing)
    }

    const results: AggregatedMetric[] = []
    for (const [category, group] of grouped) {
      const values = group.map((m) => m.value)
      const sum = values.reduce((a, b) => a + b, 0)
      const count = values.length
      results.push({
        id: generateId("agg"),
        name: `category:${category}`,
        category,
        unit: group[0].unit,
        aggregation: "category",
        value: sum / count,
        count,
        min: Math.min(...values),
        max: Math.max(...values),
        sum,
        avg: sum / count,
        timestamp: new Date().toISOString(),
        dimensions: [],
      })
    }
    return results
  },

  async aggregateByWorker(metrics: AnalyticsMetric[]): Promise<AggregatedMetric[]> {
    const workerMetrics = metrics.filter((m) => m.dimensions.some((d) => d.name === "worker"))
    const grouped = new Map<string, AnalyticsMetric[]>()
    for (const metric of workerMetrics) {
      const worker = metric.dimensions.find((d) => d.name === "worker")?.value ?? "unknown"
      const existing = grouped.get(worker) ?? []
      existing.push(metric)
      grouped.set(worker, existing)
    }

    const results: AggregatedMetric[] = []
    for (const [worker, group] of grouped) {
      const values = group.map((m) => m.value)
      const sum = values.reduce((a, b) => a + b, 0)
      const count = values.length
      results.push({
        id: generateId("agg"),
        name: `worker:${worker}`,
        category: group[0].category,
        unit: group[0].unit,
        aggregation: "worker",
        value: sum / count,
        count,
        min: Math.min(...values),
        max: Math.max(...values),
        sum,
        avg: sum / count,
        timestamp: new Date().toISOString(),
        dimensions: [{ name: "worker", value: worker }],
      })
    }
    return results
  },

  async aggregateByMission(metrics: AnalyticsMetric[]): Promise<AggregatedMetric[]> {
    const missionMetrics = metrics.filter((m) => m.dimensions.some((d) => d.name === "mission"))
    const grouped = new Map<string, AnalyticsMetric[]>()
    for (const metric of missionMetrics) {
      const mission = metric.dimensions.find((d) => d.name === "mission")?.value ?? "unknown"
      const existing = grouped.get(mission) ?? []
      existing.push(metric)
      grouped.set(mission, existing)
    }

    const results: AggregatedMetric[] = []
    for (const [mission, group] of grouped) {
      const values = group.map((m) => m.value)
      const sum = values.reduce((a, b) => a + b, 0)
      const count = values.length
      results.push({
        id: generateId("agg"),
        name: `mission:${mission}`,
        category: group[0].category,
        unit: group[0].unit,
        aggregation: "mission",
        value: sum / count,
        count,
        min: Math.min(...values),
        max: Math.max(...values),
        sum,
        avg: sum / count,
        timestamp: new Date().toISOString(),
        dimensions: [{ name: "mission", value: mission }],
      })
    }
    return results
  },

  async getAggregation(id: string): Promise<AggregatedMetric | null> {
    return aggregations.get(id) ?? null
  },

  async getAggregationCount(): Promise<number> {
    return aggregations.size
  },
}
