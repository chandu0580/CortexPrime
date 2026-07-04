import type { ConnectorDefinition, ConnectorIdentity, ConnectorType, ConnectorState, ConnectorStatus, ConnectorCapability, ConnectorEndpoint, ConnectorPermission, ConnectorRegistration } from "./types"
import { generateId } from "./shared"

const registrations = new Map<string, ConnectorRegistration>()

export const ConnectorRegistry = {
  async register(
    identity: ConnectorIdentity,
    type: ConnectorType,
    capabilities: ConnectorCapability[],
    endpoints: ConnectorEndpoint[],
    permissions: ConnectorPermission[]
  ): Promise<ConnectorRegistration> {
    const now = new Date().toISOString()
    const definition: ConnectorDefinition = {
      id: generateId("conn"),
      name: identity.name,
      version: identity.version,
      type,
      identity,
      metadata: {
        displayName: identity.name,
        description: identity.description,
        category: "connector",
        icon: "",
        documentationUrl: "",
        supportUrl: "",
        tags: [],
      },
      capabilities,
      endpoints,
      permissions,
      state: "initialized",
      status: "unknown",
      createdAt: now,
      updatedAt: now,
    }
    const registration: ConnectorRegistration = {
      connectorId: definition.id,
      definition,
      registeredAt: now,
      lastSeenAt: now,
    }
    registrations.set(definition.id, registration)
    return registration
  },

  async unregister(connectorId: string): Promise<void> {
    registrations.delete(connectorId)
  },

  async lookup(connectorId: string): Promise<ConnectorDefinition | null> {
    return registrations.get(connectorId)?.definition ?? null
  },

  async list(): Promise<ConnectorDefinition[]> {
    return Array.from(registrations.values()).map((r) => r.definition)
  },

  async discover(criteria: Partial<ConnectorDefinition>): Promise<ConnectorDefinition[]> {
    return Array.from(registrations.values())
      .map((r) => r.definition)
      .filter((d) => {
        for (const [key, value] of Object.entries(criteria)) {
          if (value !== undefined && (d as unknown as Record<string, unknown>)[key] !== value) {
            return false
          }
        }
        return true
      })
  },

  async registrationCount(): Promise<number> {
    return registrations.size
  },
}
