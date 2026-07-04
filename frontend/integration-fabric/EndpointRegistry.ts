import type { ConnectorEndpoint, EndpointDefinition, EndpointType } from "./types"
import { generateId } from "./shared"

const endpoints = new Map<string, ConnectorEndpoint>()
const definitions = new Map<string, EndpointDefinition>()

export const EndpointRegistry = {
  async registerEndpoint(
    connectorId: string,
    name: string,
    type: EndpointType,
    url: string,
    credentialRef: string | null = null,
    config: Record<string, unknown> = {},
  ): Promise<ConnectorEndpoint> {
    const id = generateId("ep")
    const endpoint: ConnectorEndpoint = {
      id,
      connectorId,
      name,
      type,
      url,
      credentialRef,
      config,
      enabled: true,
    }
    endpoints.set(id, endpoint)
    return endpoint
  },

  async updateEndpoint(endpointId: string, updates: Partial<ConnectorEndpoint>): Promise<ConnectorEndpoint> {
    const endpoint = endpoints.get(endpointId)
    if (!endpoint) throw new Error(`Endpoint not found: ${endpointId}`)
    const updated: ConnectorEndpoint = { ...endpoint, ...updates, id: endpointId }
    endpoints.set(endpointId, updated)
    return updated
  },

  async removeEndpoint(endpointId: string): Promise<void> {
    if (!endpoints.has(endpointId)) throw new Error(`Endpoint not found: ${endpointId}`)
    endpoints.delete(endpointId)
  },

  async queryEndpoints(connectorId?: string, type?: EndpointType, enabled?: boolean): Promise<ConnectorEndpoint[]> {
    let result = Array.from(endpoints.values())
    if (connectorId) result = result.filter((e) => e.connectorId === connectorId)
    if (type) result = result.filter((e) => e.type === type)
    if (enabled !== undefined) result = result.filter((e) => e.enabled === enabled)
    return result
  },

  async getEndpoint(endpointId: string): Promise<ConnectorEndpoint | null> {
    return endpoints.get(endpointId) ?? null
  },

  async registerDefinition(
    name: string,
    type: EndpointType,
    baseUrl: string,
    methods: string[] = [],
    headers: Record<string, string> = {},
    timeout: number = 30000,
    retryCount: number = 3,
  ): Promise<EndpointDefinition> {
    const id = generateId("ep-def")
    const definition: EndpointDefinition = {
      id,
      name,
      type,
      baseUrl,
      version: "1.0.0",
      methods,
      headers,
      timeout,
      retryCount,
    }
    definitions.set(id, definition)
    return definition
  },

  async getDefinition(definitionId: string): Promise<EndpointDefinition | null> {
    return definitions.get(definitionId) ?? null
  },

  async endpointCount(): Promise<number> {
    return endpoints.size
  },
}
