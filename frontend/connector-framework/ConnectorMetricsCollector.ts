import type { ConnectorMetric, ValveMetrics } from "./types"
import { generateId } from "./shared"

const metricsStore = new Map<string, ConnectorMetric[]>()

export const ConnectorMetricsCollector = {
  async collectConnectorMetric(
    connectorId: string,
    name: string,
    value: number,
    unit: string,
    labels: Record<string, string> = {}
  ): Promise<ConnectorMetric> {
    const metric: ConnectorMetric = {
      id: generateId("metric"),
      connectorId,
      name,
      value,
      unit,
      timestamp: new Date().toISOString(),
      labels,
    }
    const existing = metricsStore.get(connectorId) ?? []
    existing.push(metric)
    metricsStore.set(connectorId, existing)
    return metric
  },

  async aggregateMetrics(connectorId: string): Promise<ValveMetrics> {
    const metrics = metricsStore.get(connectorId) ?? []
    const totalConnectors = metrics.filter((m) => m.name === "connectors").reduce((s, m) => s + m.value, 0)
    const activeConnectors = metrics.filter((m) => m.name === "active_connectors").reduce((s, m) => s + m.value, 0)
    const totalSessions = metrics.filter((m) => m.name === "sessions").reduce((s, m) => s + m.value, 0)
    const totalCapabilities = metrics.filter((m) => m.name === "capabilities").reduce((s, m) => s + m.value, 0)
    const totalLifecycleEvents = metrics.filter((m) => m.name === "lifecycle_events").reduce((s, m) => s + m.value, 0)
    const totalValidations = metrics.filter((m) => m.name === "validations").reduce((s, m) => s + m.value, 0)
    const totalEndpoints = metrics.filter((m) => m.name === "endpoints").reduce((s, m) => s + m.value, 0)
    const totalPermissions = metrics.filter((m) => m.name === "permissions").reduce((s, m) => s + m.value, 0)

    return {
      totalConnectors,
      activeConnectors,
      totalSessions,
      totalCapabilities,
      totalLifecycleEvents,
      totalValidations,
      totalEndpoints,
      totalPermissions,
    }
  },

  async getMetrics(connectorId: string): Promise<ConnectorMetric[]> {
    return metricsStore.get(connectorId) ?? []
  },
}
