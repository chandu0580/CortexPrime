import { ConnectorCapabilityDefinition } from "../../connector-framework/types"

export const ConfluenceCapabilityDefinitions: ConnectorCapabilityDefinition[] = [
  {
    id: "confluence-spaces",
    name: "confluence.spaces",
    description: "Manage Confluence spaces",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "confluence-pages",
    name: "confluence.pages",
    description: "Manage Confluence pages",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "confluence-blogs",
    name: "confluence.blogs",
    description: "Manage Confluence blog posts",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "confluence-attachments",
    name: "confluence.attachments",
    description: "Manage Confluence attachments",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "confluence-search",
    name: "confluence.search",
    description: "Search Confluence content",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "confluence-permissions",
    name: "confluence.permissions",
    description: "Evaluate Confluence permissions",
    version: "1.0.0",
    enabled: true,
  },
]

export const ConfluenceCapability = {
  async getDefinitions(): Promise<ConnectorCapabilityDefinition[]> {
    return [...ConfluenceCapabilityDefinitions]
  },

  async getDefinition(name: string): Promise<ConnectorCapabilityDefinition | undefined> {
    return ConfluenceCapabilityDefinitions.find((d) => d.name === name)
  },
}