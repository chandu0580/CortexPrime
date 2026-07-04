import type { ConnectorHealth, ConnectorStatus, ConnectorState, ValveHealth } from "./types"
import { generateId } from "./shared"

const healthRecords = new Map<string, ConnectorHealth>()

export const ConnectorHealthManager = {
  async check(
    connectorId: string,
    state: ConnectorState,
    uptimeMs: number,
    lastError: string | null,
    details: Record<string, unknown> = {}
  ): Promise<ConnectorHealth> {
    const existing = healthRecords.get(connectorId)

    let status: ConnectorStatus
    if (state === "deactivated") {
      status = "unknown"
    } else if (state === "active") {
      status = existing?.status === "healthy" ? "healthy" : "degraded"
    } else if (state === "paused") {
      status = "degraded"
    } else {
      status = "unhealthy"
    }

    const health: ConnectorHealth = {
      status,
      state,
      uptimeMs,
      lastHeartbeat: new Date().toISOString(),
      lastError,
      details,
    }
    healthRecords.set(connectorId, health)
    return health
  },

  async aggregateHealth(healths: ConnectorHealth[]): Promise<ValveHealth> {
    const unhealthy = healths.filter((h) => h.status === "unhealthy")
    const degraded = healths.filter((h) => h.status === "degraded")

    const inactiveConnectors = healths.filter((h) => h.state === "deactivated" || h.state === "failed").length
    const validationFailures = healths.filter((h) => h.lastError !== null).length
    const lifecycleFailures = healths.filter((h) => h.state === "failed").length
    const capabilityFailures = healths.filter((h) => h.status === "unhealthy").length

    let status: ValveHealth["status"] = "healthy"
    if (unhealthy.length > 0) {
      status = "unhealthy"
    } else if (degraded.length > 0) {
      status = "degraded"
    }

    return {
      status,
      inactiveConnectors,
      validationFailures,
      lifecycleFailures,
      capabilityFailures,
      lastSnapshot: new Date().toISOString(),
    }
  },

  async getHealth(connectorId: string): Promise<ConnectorHealth | null> {
    return healthRecords.get(connectorId) ?? null
  },

  async isHealthy(connectorId: string): Promise<boolean> {
    return healthRecords.get(connectorId)?.status === "healthy"
  },

  async recordHeartbeat(connectorId: string, state: ConnectorState): Promise<string> {
    const existing = healthRecords.get(connectorId)
    const health: ConnectorHealth = {
      status: existing?.status ?? "unknown",
      state,
      uptimeMs: existing?.uptimeMs ?? 0,
      lastHeartbeat: new Date().toISOString(),
      lastError: null,
      details: {},
    }
    healthRecords.set(connectorId, health)
    return health.lastHeartbeat as string
  },
}
