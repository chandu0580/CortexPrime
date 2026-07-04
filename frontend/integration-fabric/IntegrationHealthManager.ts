import type { IntegrationHealth, HealthSnapshot } from "./types"

const healthSnapshots: HealthSnapshot[] = []

let inactiveConnectors = 0
let failedSyncs = 0
let endpointFailures = 0
let routingFailures = 0
let credentialIssues = 0

export const IntegrationHealthManager = {
  async recordInactiveConnector(): Promise<void> {
    inactiveConnectors++
  },

  async recordFailedSync(): Promise<void> {
    failedSyncs++
  },

  async recordEndpointFailure(): Promise<void> {
    endpointFailures++
  },

  async recordRoutingFailure(): Promise<void> {
    routingFailures++
  },

  async recordCredentialIssue(): Promise<void> {
    credentialIssues++
  },

  async snapshot(component: string, metrics: Record<string, number>, details: string = ""): Promise<HealthSnapshot> {
    const totalFailures = inactiveConnectors + failedSyncs + endpointFailures + routingFailures + credentialIssues
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

  async getHealth(): Promise<IntegrationHealth> {
    const totalFailures = inactiveConnectors + failedSyncs + endpointFailures + routingFailures + credentialIssues
    const status: "healthy" | "degraded" | "unhealthy" = totalFailures === 0 ? "healthy" : totalFailures > 10 ? "unhealthy" : "degraded"

    return {
      status,
      inactiveConnectors,
      failedSyncs,
      endpointFailures,
      routingFailures,
      credentialIssues,
      lastSnapshot: healthSnapshots.length > 0 ? healthSnapshots[healthSnapshots.length - 1].timestamp : null,
    }
  },

  async getSnapshots(component?: string, limit: number = 50): Promise<HealthSnapshot[]> {
    let result = [...healthSnapshots]
    if (component) result = result.filter((s) => s.component === component)
    return result.slice(-limit).reverse()
  },

  async resetCounters(): Promise<void> {
    inactiveConnectors = 0
    failedSyncs = 0
    endpointFailures = 0
    routingFailures = 0
    credentialIssues = 0
  },
}
