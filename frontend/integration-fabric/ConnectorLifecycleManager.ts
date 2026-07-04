import type { IntegrationConnector, ConnectorState } from "./types"
import { generateId } from "./shared"
import { ConnectorRegistry } from "./ConnectorRegistry"

const registrations = new Map<string, { connectorId: string; state: ConnectorState; message: string; timestamp: string }[]>()

export const ConnectorLifecycleManager = {
  async initializeConnector(connectorId: string): Promise<IntegrationConnector> {
    const connector = await ConnectorRegistry.getConnector(connectorId)
    if (!connector) throw new Error(`Connector not found: ${connectorId}`)
    const updated = await ConnectorRegistry.updateConnector(connectorId, { state: "initialized" })
    await ConnectorLifecycleManager.recordTransition(connectorId, "initialized", "Connector initialized")
    return updated
  },

  async activateConnector(connectorId: string): Promise<IntegrationConnector> {
    const connector = await ConnectorRegistry.getConnector(connectorId)
    if (!connector) throw new Error(`Connector not found: ${connectorId}`)
    const updated = await ConnectorRegistry.updateConnector(connectorId, { state: "active" })
    await ConnectorLifecycleManager.recordTransition(connectorId, "active", "Connector activated")
    return updated
  },

  async pauseConnector(connectorId: string): Promise<IntegrationConnector> {
    const connector = await ConnectorRegistry.getConnector(connectorId)
    if (!connector) throw new Error(`Connector not found: ${connectorId}`)
    const updated = await ConnectorRegistry.updateConnector(connectorId, { state: "paused" })
    await ConnectorLifecycleManager.recordTransition(connectorId, "paused", "Connector paused")
    return updated
  },

  async resumeConnector(connectorId: string): Promise<IntegrationConnector> {
    const connector = await ConnectorRegistry.getConnector(connectorId)
    if (!connector) throw new Error(`Connector not found: ${connectorId}`)
    const updated = await ConnectorRegistry.updateConnector(connectorId, { state: "active" })
    await ConnectorLifecycleManager.recordTransition(connectorId, "active", "Connector resumed")
    return updated
  },

  async deactivateConnector(connectorId: string): Promise<IntegrationConnector> {
    const connector = await ConnectorRegistry.getConnector(connectorId)
    if (!connector) throw new Error(`Connector not found: ${connectorId}`)
    const updated = await ConnectorRegistry.updateConnector(connectorId, { state: "deactivated" })
    await ConnectorLifecycleManager.recordTransition(connectorId, "deactivated", "Connector deactivated")
    return updated
  },

  async recordTransition(connectorId: string, state: ConnectorState, message: string): Promise<void> {
    const transitions = registrations.get(connectorId) ?? []
    transitions.push({ connectorId, state, message, timestamp: new Date().toISOString() })
    registrations.set(connectorId, transitions)
  },

  async getTransitions(connectorId: string): Promise<{ connectorId: string; state: ConnectorState; message: string; timestamp: string }[]> {
    return registrations.get(connectorId) ?? []
  },

  async getConnectorState(connectorId: string): Promise<ConnectorState | null> {
    const connector = await ConnectorRegistry.getConnector(connectorId)
    return connector?.state ?? null
  },
}
