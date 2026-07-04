import type { AnalyticsHealth, HealthSnapshot } from "./types"

const healthSnapshots: HealthSnapshot[] = []

let aggregationFailures = 0
let kpiFailures = 0
let reportingFailures = 0
let insightFailures = 0

export const AnalyticsHealthManager = {
  async recordAggregationFailure(): Promise<void> {
    aggregationFailures++
  },

  async recordKPIFailure(): Promise<void> {
    kpiFailures++
  },

  async recordReportingFailure(): Promise<void> {
    reportingFailures++
  },

  async recordInsightFailure(): Promise<void> {
    insightFailures++
  },

  async snapshot(component: string, metrics: Record<string, number>, details: string = ""): Promise<HealthSnapshot> {
    const totalFailures = aggregationFailures + kpiFailures + reportingFailures + insightFailures
    const status: "healthy" | "degraded" | "unhealthy" = totalFailures === 0 ? "healthy" : totalFailures > 10 ? "unhealthy" : "degraded"

    const snapshot: HealthSnapshot = {
      timestamp: new Date().toISOString(),
      component,
      status,
      metrics,
      details,
    }
    healthSnapshots.push(snapshot)
    return snapshot
  },

  async getHealth(): Promise<AnalyticsHealth> {
    const totalFailures = aggregationFailures + kpiFailures + reportingFailures + insightFailures
    const status: "healthy" | "degraded" | "unhealthy" = totalFailures === 0 ? "healthy" : totalFailures > 10 ? "unhealthy" : "degraded"

    return {
      status,
      aggregationFailures,
      kpiFailures,
      reportingFailures,
      insightFailures,
      recoveryReady: totalFailures < 5,
      lastSnapshot: healthSnapshots.length > 0 ? healthSnapshots[healthSnapshots.length - 1].timestamp : null,
    }
  },

  async getSnapshots(component?: string, limit: number = 50): Promise<HealthSnapshot[]> {
    let result = [...healthSnapshots]
    if (component) result = result.filter((s) => s.component === component)
    return result.slice(-limit).reverse()
  },

  async resetCounters(): Promise<void> {
    aggregationFailures = 0
    kpiFailures = 0
    reportingFailures = 0
    insightFailures = 0
  },
}
