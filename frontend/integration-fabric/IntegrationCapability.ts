import type { IntegrationCapabilityDefinition } from "./types"
import { generateId } from "./shared"

const capabilities = new Map<string, IntegrationCapabilityDefinition>()

const builtInCapabilities: IntegrationCapabilityDefinition[] = [
  { id: "int-connector", name: "integration.connector", description: "Connector registration, lifecycle, and capability resolution", version: "1.0.0", enabled: true },
  { id: "int-endpoint", name: "integration.endpoint", description: "Endpoint registration, definition, and query management", version: "1.0.0", enabled: true },
  { id: "int-routing", name: "integration.routing", description: "Event routing between connectors with publish/subscribe", version: "1.0.0", enabled: true },
  { id: "int-sync", name: "integration.sync", description: "Synchronization planning, scheduling, and job execution", version: "1.0.0", enabled: true },
  { id: "int-credentials", name: "integration.credentials", description: "Credential reference lifecycle and validation", version: "1.0.0", enabled: true },
  { id: "int-validation", name: "integration.validation", description: "Integration validation for connectors, endpoints, sync, routing, credentials", version: "1.0.0", enabled: true },
]

for (const cap of builtInCapabilities) {
  capabilities.set(cap.id, cap)
}

export const IntegrationCapability = {
  async isEnabled(name: string): Promise<boolean> {
    const cap = Array.from(capabilities.values()).find((c) => c.name === name)
    return cap?.enabled ?? false
  },

  async enable(name: string): Promise<IntegrationCapabilityDefinition> {
    const cap = Array.from(capabilities.values()).find((c) => c.name === name)
    if (!cap) throw new Error(`Capability not found: ${name}`)
    const updated: IntegrationCapabilityDefinition = { ...cap, enabled: true }
    capabilities.set(cap.id, updated)
    return updated
  },

  async disable(name: string): Promise<IntegrationCapabilityDefinition> {
    const cap = Array.from(capabilities.values()).find((c) => c.name === name)
    if (!cap) throw new Error(`Capability not found: ${name}`)
    const updated: IntegrationCapabilityDefinition = { ...cap, enabled: false }
    capabilities.set(cap.id, updated)
    return updated
  },

  async register(definition: Omit<IntegrationCapabilityDefinition, "id">): Promise<IntegrationCapabilityDefinition> {
    const id = generateId("cap")
    const full: IntegrationCapabilityDefinition = { ...definition, id }
    capabilities.set(id, full)
    return full
  },

  async list(): Promise<IntegrationCapabilityDefinition[]> {
    return Array.from(capabilities.values())
  },

  async get(name: string): Promise<IntegrationCapabilityDefinition | null> {
    return Array.from(capabilities.values()).find((c) => c.name === name) ?? null
  },
}
