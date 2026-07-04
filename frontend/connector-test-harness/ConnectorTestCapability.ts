import type { ConnectorCapabilityDefinition } from "../connector-framework/types"

export const ConnectorTestCapabilityDefinitions: ConnectorCapabilityDefinition[] = [
  {
    id: "test-validation",
    name: "connector.validation",
    description: "Validate connector implementations",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "test-contracts",
    name: "connector.contracts",
    description: "Validate connector contracts",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "test-health",
    name: "connector.health",
    description: "Validate connector health reporting",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "test-metrics",
    name: "connector.metrics",
    description: "Validate connector metrics",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "test-events",
    name: "connector.events",
    description: "Validate connector events",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "test-reporting",
    name: "connector.reporting",
    description: "Generate validation reports",
    version: "1.0.0",
    enabled: true,
  },
]

export const ConnectorTestCapability = {
  async getDefinitions(): Promise<ConnectorCapabilityDefinition[]> {
    return [...ConnectorTestCapabilityDefinitions]
  },

  async getDefinition(name: string): Promise<ConnectorCapabilityDefinition | undefined> {
    return ConnectorTestCapabilityDefinitions.find((d) => d.name === name)
  },
}