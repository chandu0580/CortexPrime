import type { IntegrationConnector, ConnectorDescriptor, ConnectorCapability, ConnectorEndpoint, ConnectorType, ConnectorState } from "./types"
import { generateId } from "./shared"

const connectors = new Map<string, IntegrationConnector>()

export const ConnectorRegistry = {
  async registerConnector(
    name: string,
    type: ConnectorType,
    descriptor: ConnectorDescriptor,
    capabilities: ConnectorCapability[] = [],
    endpoints: ConnectorEndpoint[] = [],
    metadata: Record<string, unknown> = {},
  ): Promise<IntegrationConnector> {
    if (Array.from(connectors.values()).some((c) => c.name === name)) {
      throw new Error(`Connector already registered: ${name}`)
    }
    const id = generateId("conn")
    const now = new Date().toISOString()
    const connector: IntegrationConnector = {
      id,
      name,
      version: descriptor.version,
      type,
      state: "initialized",
      descriptor,
      capabilities,
      endpoints,
      metadata,
      createdAt: now,
      updatedAt: now,
    }
    connectors.set(id, connector)
    return connector
  },

  async unregisterConnector(connectorId: string): Promise<void> {
    if (!connectors.has(connectorId)) throw new Error(`Connector not found: ${connectorId}`)
    connectors.delete(connectorId)
  },

  async getConnector(connectorId: string): Promise<IntegrationConnector | null> {
    return connectors.get(connectorId) ?? null
  },

  async listConnectors(type?: ConnectorType, state?: ConnectorState): Promise<IntegrationConnector[]> {
    let result = Array.from(connectors.values())
    if (type) result = result.filter((c) => c.type === type)
    if (state) result = result.filter((c) => c.state === state)
    return result.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
  },

  async updateConnector(connectorId: string, updates: Partial<IntegrationConnector>): Promise<IntegrationConnector> {
    const connector = connectors.get(connectorId)
    if (!connector) throw new Error(`Connector not found: ${connectorId}`)
    const updated: IntegrationConnector = { ...connector, ...updates, id: connectorId, updatedAt: new Date().toISOString() }
    connectors.set(connectorId, updated)
    return updated
  },

  async connectorCount(): Promise<number> {
    return connectors.size
  },
}
