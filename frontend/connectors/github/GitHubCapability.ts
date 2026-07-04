import { ConnectorCapabilityDefinition } from "../../connector-framework/types"

export const GitHubCapabilityDefinitions: ConnectorCapabilityDefinition[] = [
  {
    id: "github-repositories",
    name: "github.repositories",
    description: "Manage GitHub repositories",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "github-issues",
    name: "github.issues",
    description: "Manage GitHub issues",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "github-pull-requests",
    name: "github.pull_requests",
    description: "Manage GitHub pull requests",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "github-actions",
    name: "github.actions",
    description: "Manage GitHub Actions workflows",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "github-projects",
    name: "github.projects",
    description: "Manage GitHub projects",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "github-security",
    name: "github.security",
    description: "Evaluate GitHub security policies",
    version: "1.0.0",
    enabled: true,
  },
]

export const GitHubCapability = {
  async getDefinitions(): Promise<ConnectorCapabilityDefinition[]> {
    return [...GitHubCapabilityDefinitions]
  },

  async getDefinition(name: string): Promise<ConnectorCapabilityDefinition | undefined> {
    return GitHubCapabilityDefinitions.find((d) => d.name === name)
  },
}
