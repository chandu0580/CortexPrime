import type { CoordinationHealth, HealthSnapshot } from "./types"

const healthSnapshots: HealthSnapshot[] = []

let failedDelegations = 0
let syncFailures = 0
let routingFailures = 0
let coordinationFailures = 0

export const CoordinationHealthManager = {
  async recordFailedDelegation(): Promise<void> {
    failedDelegations++
  },

  async recordSyncFailure(): Promise<void> {
    syncFailures++
  },

  async recordRoutingFailure(): Promise<void> {
    routingFailures++
  },

  async recordCoordinationFailure(): Promise<void> {
    coordinationFailures++
  },

  async snapshot(component: string, metrics: Record<string, number>, details: string = ""): Promise<HealthSnapshot> {
    const totalFailures = failedDelegations + syncFailures + routingFailures + coordinationFailures
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

  async getHealth(): Promise<CoordinationHealth> {
    const totalFailures = failedDelegations + syncFailures + routingFailures + coordinationFailures
    const status: "healthy" | "degraded" | "unhealthy" = totalFailures === 0 ? "healthy" : totalFailures > 10 ? "unhealthy" : "degraded"

    return {
      status,
      failedDelegations,
      syncFailures,
      routingFailures,
      coordinationFailures,
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
    failedDelegations = 0
    syncFailures = 0
    routingFailures = 0
    coordinationFailures = 0
  },
}
