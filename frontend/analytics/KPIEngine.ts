import type { KPI, KPIThreshold, KPIStatus, TrendDirection, AggregatedMetric } from "./types"
import { generateId } from "./shared"

const kpis = new Map<string, KPI>()

export const KPIEngine = {
  async calculateKPIs(metrics: AggregatedMetric[], thresholds: Map<string, KPIThreshold>): Promise<KPI[]> {
    const results: KPI[] = []

    for (const metric of metrics) {
      const threshold = thresholds.get(metric.name) ?? KPIEngine.defaultThreshold()
      const status = KPIEngine.evaluateThreshold(metric.avg, threshold)
      const trend: TrendDirection = "flat"

      const kpi: KPI = {
        id: generateId("kpi"),
        name: metric.name,
        description: `KPI for ${metric.name}`,
        category: metric.category,
        value: metric.avg,
        target: (threshold.goodMin + threshold.goodMax) / 2,
        unit: metric.unit,
        status,
        threshold,
        timestamp: new Date().toISOString(),
        trend,
      }
      kpis.set(kpi.id, kpi)
      results.push(kpi)
    }

    return results
  },

  defaultThreshold(): KPIThreshold {
    return { goodMin: 0, goodMax: 100, warningMin: -Infinity, warningMax: Infinity }
  },

  evaluateThreshold(value: number, threshold: KPIThreshold): KPIStatus {
    if (value >= threshold.goodMin && value <= threshold.goodMax) return "good"
    if (value >= threshold.warningMin && value <= threshold.warningMax) return "warning"
    return "critical"
  },

  async evaluateThresholds(kpisToEvaluate: KPI[]): Promise<KPI[]> {
    return kpisToEvaluate.map((kpi) => ({
      ...kpi,
      status: KPIEngine.evaluateThreshold(kpi.value, kpi.threshold),
    }))
  },

  async rankKPIs(kpisToRank: KPI[]): Promise<KPI[]> {
    const severityOrder: Record<KPIStatus, number> = { critical: 0, warning: 1, good: 2, unknown: 3 }
    return [...kpisToRank].sort((a, b) => severityOrder[a.status] - severityOrder[b.status])
  },

  async summarizeKPIs(kpisToSummarize: KPI[]): Promise<{ total: number; good: number; warning: number; critical: number; unknown: number; healthScore: number }> {
    const total = kpisToSummarize.length
    const good = kpisToSummarize.filter((k) => k.status === "good").length
    const warning = kpisToSummarize.filter((k) => k.status === "warning").length
    const critical = kpisToSummarize.filter((k) => k.status === "critical").length
    const unknown = kpisToSummarize.filter((k) => k.status === "unknown").length
    const healthScore = total === 0 ? 0 : Math.round((good / total) * 100)
    return { total, good, warning, critical, unknown, healthScore }
  },

  async getKPI(id: string): Promise<KPI | null> {
    return kpis.get(id) ?? null
  },

  async listKPIs(category?: string): Promise<KPI[]> {
    let result = Array.from(kpis.values())
    if (category) result = result.filter((k) => k.category === category)
    return result
  },

  async kpiCount(): Promise<number> {
    return kpis.size
  },
}
