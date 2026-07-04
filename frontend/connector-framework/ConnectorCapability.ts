import type { ConnectorCapabilityDefinition, ConnectorCapability as ConnectorCapabilityType } from "./types"
import { ConnectorCapabilityManager } from "./ConnectorCapabilityManager"

const definitions: ConnectorCapabilityDefinition[] = [
  {
    id: "capdef-lifecycle",
    name: "connector.lifecycle",
    description: "Manage connector lifecycle operations",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "capdef-capabilities",
    name: "connector.capabilities",
    description: "Manage connector capabilities",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "capdef-configuration",
    name: "connector.configuration",
    description: "Manage connector configuration",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "capdef-validation",
    name: "connector.validation",
    description: "Validate connector integrity",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "capdef-health",
    name: "connector.health",
    description: "Monitor connector health",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "capdef-metrics",
    name: "connector.metrics",
    description: "Collect connector metrics",
    version: "1.0.0",
    enabled: true,
  },
]

export const ConnectorCapabilityService = {
  async getDefinitions(): Promise<ConnectorCapabilityDefinition[]> {
    return [...definitions]
  },

  async getDefinition(name: string): Promise<ConnectorCapabilityDefinition | undefined> {
    return definitions.find((d) => d.name === name)
  },

  async registerCapability(
    name: string,
    description: string,
    version: string,
    config: Record<string, unknown> = {}
  ): Promise<ConnectorCapabilityType> {
    return ConnectorCapabilityManager.registerCapability(name, description, version, config)
  },
}
