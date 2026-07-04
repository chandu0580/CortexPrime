import { ConnectorCapabilityDefinition } from "../../connector-framework/types"

export const TeamsCapabilityDefinitions: ConnectorCapabilityDefinition[] = [
  {
    id: "teams-organizations",
    name: "teams.organizations",
    description: "Manage Teams organizations",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "teams-channels",
    name: "teams.channels",
    description: "Manage Teams channels",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "teams-messaging",
    name: "teams.messaging",
    description: "Send and manage Teams messages",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "teams-meetings",
    name: "teams.meetings",
    description: "Schedule and manage Teams meetings",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "teams-workflows",
    name: "teams.workflows",
    description: "Manage Teams workflows",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "teams-permissions",
    name: "teams.permissions",
    description: "Evaluate Teams permissions",
    version: "1.0.0",
    enabled: true,
  },
]

export const TeamsCapability = {
  async getDefinitions(): Promise<ConnectorCapabilityDefinition[]> {
    return [...TeamsCapabilityDefinitions]
  },

  async getDefinition(name: string): Promise<ConnectorCapabilityDefinition | undefined> {
    return TeamsCapabilityDefinitions.find((d) => d.name === name)
  },
}