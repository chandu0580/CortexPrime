import { ConnectorCapabilityDefinition } from "../../connector-framework/types"

export const AzureCapabilityDefinitions: ConnectorCapabilityDefinition[] = [
  {
    id: "azure-organizations",
    name: "azure.organizations",
    description: "Manage Azure DevOps organizations",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "azure-projects",
    name: "azure.projects",
    description: "Manage Azure DevOps projects",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "azure-boards",
    name: "azure.boards",
    description: "Manage Azure DevOps boards and work items",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "azure-repositories",
    name: "azure.repositories",
    description: "Manage Azure DevOps repositories",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "azure-pipelines",
    name: "azure.pipelines",
    description: "Manage Azure DevOps pipelines",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "azure-artifacts",
    name: "azure.artifacts",
    description: "Manage Azure DevOps artifacts and feeds",
    version: "1.0.0",
    enabled: true,
  },
]

export const AzureCapability = {
  async getDefinitions(): Promise<ConnectorCapabilityDefinition[]> {
    return [...AzureCapabilityDefinitions]
  },

  async getDefinition(name: string): Promise<ConnectorCapabilityDefinition | undefined> {
    return AzureCapabilityDefinitions.find((d) => d.name === name)
  },
}