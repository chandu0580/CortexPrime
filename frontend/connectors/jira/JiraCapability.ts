import { ConnectorCapabilityDefinition } from "../../connector-framework/types"

export const JiraCapabilityDefinitions: ConnectorCapabilityDefinition[] = [
  {
    id: "jira-projects",
    name: "jira.projects",
    description: "Manage Jira projects",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "jira-issues",
    name: "jira.issues",
    description: "Manage Jira issues",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "jira-sprints",
    name: "jira.sprints",
    description: "Manage Jira sprints",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "jira-workflows",
    name: "jira.workflows",
    description: "Manage Jira workflows",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "jira-releases",
    name: "jira.releases",
    description: "Manage Jira releases",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "jira-permissions",
    name: "jira.permissions",
    description: "Evaluate Jira permissions",
    version: "1.0.0",
    enabled: true,
  },
]

export const JiraCapability = {
  async getDefinitions(): Promise<ConnectorCapabilityDefinition[]> {
    return [...JiraCapabilityDefinitions]
  },

  async getDefinition(name: string): Promise<ConnectorCapabilityDefinition | undefined> {
    return JiraCapabilityDefinitions.find((d) => d.name === name)
  },
}
