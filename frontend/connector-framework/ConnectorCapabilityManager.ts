import type { ConnectorCapability, ConnectorCapabilityDefinition } from "./types"
import { generateId } from "./shared"

export const ConnectorCapabilityManager = {
  async registerCapability(
    name: string,
    description: string,
    version: string,
    config: Record<string, unknown> = {}
  ): Promise<ConnectorCapability> {
    return {
      id: generateId("cap"),
      name,
      description,
      version,
      supported: true,
      config,
    }
  },

  async removeCapability(capabilities: ConnectorCapability[], id: string): Promise<ConnectorCapability[]> {
    return capabilities.filter((c) => c.id !== id)
  },

  async resolveCapability(capabilities: ConnectorCapability[], name: string): Promise<ConnectorCapability | null> {
    return capabilities.find((c) => c.name === name) ?? null
  },

  async validateCapability(capability: ConnectorCapability): Promise<string[]> {
    const errors: string[] = []
    if (!capability.id) errors.push("capability id is required")
    if (!capability.name) errors.push("capability name is required")
    if (!capability.version) errors.push("capability version is required")
    return errors
  },

  async createCapabilityDefinition(
    name: string,
    description: string,
    version: string,
    enabled = true
  ): Promise<ConnectorCapabilityDefinition> {
    return {
      id: generateId("capdef"),
      name,
      description,
      version,
      enabled,
    }
  },
}
