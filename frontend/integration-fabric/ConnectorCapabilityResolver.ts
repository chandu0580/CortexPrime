import type { ConnectorCapability } from "./types"
import { generateId } from "./shared"

const capabilityDefinitions = new Map<string, ConnectorCapability>()

export const ConnectorCapabilityResolver = {
  async resolveCapabilities(connectorCapabilities: ConnectorCapability[]): Promise<ConnectorCapability[]> {
    return connectorCapabilities.filter((c) => c.supported)
  },

  async validateCapabilities(required: string[], available: ConnectorCapability[]): Promise<{ valid: boolean; missing: string[] }> {
    const names = new Set(available.filter((c) => c.supported).map((c) => c.name))
    const missing = required.filter((r) => !names.has(r))
    return { valid: missing.length === 0, missing }
  },

  async discoverCapabilities(descriptorName: string, descriptorDescription: string): Promise<ConnectorCapability[]> {
    const cached = Array.from(capabilityDefinitions.values())
    if (cached.length > 0) return cached

    const builtIn: ConnectorCapability[] = [
      { id: generateId("cap"), name: "read", description: "Read data from external system", version: "1.0.0", supported: true },
      { id: generateId("cap"), name: "write", description: "Write data to external system", version: "1.0.0", supported: true },
      { id: generateId("cap"), name: "subscribe", description: "Subscribe to events from external system", version: "1.0.0", supported: true },
      { id: generateId("cap"), name: "query", description: "Query external system for data", version: "1.0.0", supported: true },
      { id: generateId("cap"), name: "synchronize", description: "Synchronize data between systems", version: "1.0.0", supported: true },
      { id: generateId("cap"), name: "transform", description: "Transform data formats", version: "1.0.0", supported: true },
    ]

    for (const cap of builtIn) {
      capabilityDefinitions.set(cap.id, cap)
    }

    return builtIn
  },

  async registerCapabilityDefinition(capability: ConnectorCapability): Promise<ConnectorCapability> {
    capabilityDefinitions.set(capability.id, capability)
    return capability
  },
}
