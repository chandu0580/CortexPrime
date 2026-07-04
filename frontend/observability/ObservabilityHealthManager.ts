import type { HealthSnapshot, ObservabilityHealth } from "./types"

const healthSnapshots: HealthSnapshot[] = []

let droppedTraces = 0
let failedSpans = 0
let replayFailures = 0
let metricFailures = 0
let auditFailures = 0

export const ObservabilityHealthManager = {
  async recordDroppedTrace(): Promise<void> {
    droppedTraces++
  },

  async recordFailedSpan(): Promise<void> {
    failedSpans++
  },

  async recordReplayFailure(): Promise<void> {
    replayFailures++
  },

  async recordMetricFailure(): Promise<void> {
    metricFailures++
  },

  async recordAuditFailure(): Promise<void> {
    auditFailures++
  },

  async snapshot(component: string, metrics: Record<string, number>, details: string = ""): Promise<HealthSnapshot> {
    const totalFailures = droppedTraces + failedSpans + replayFailures + metricFailures + auditFailures
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

  async getHealth(): Promise<ObservabilityHealth> {
    const totalFailures = droppedTraces + failedSpans + replayFailures + metricFailures + auditFailures
    const status: "healthy" | "degraded" | "unhealthy" = totalFailures === 0 ? "healthy" : totalFailures > 10 ? "unhealthy" : "degraded"

    return {
      status,
      droppedTraces,
      failedSpans,
      replayFailures,
      metricFailures,
      auditFailures,
      lastSnapshot: healthSnapshots.length > 0 ? healthSnapshots[healthSnapshots.length - 1].timestamp : null,
    }
  },

  async getSnapshots(component?: string, limit: number = 50): Promise<HealthSnapshot[]> {
    let result = [...healthSnapshots]
    if (component) result = result.filter((s) => s.component === component)
    return result.slice(-limit).reverse()
  },

  async resetCounters(): Promise<void> {
    droppedTraces = 0
    failedSpans = 0
    replayFailures = 0
    metricFailures = 0
    auditFailures = 0
  },
}
