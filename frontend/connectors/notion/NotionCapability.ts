import { ConnectorCapabilityDefinition } from "../../connector-framework/types"

export const NotionCapabilityDefinitions: ConnectorCapabilityDefinition[] = [
  {
    id: "notion-workspaces",
    name: "notion.workspaces",
    description: "Manage Notion workspaces",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "notion-pages",
    name: "notion.pages",
    description: "Manage Notion pages",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "notion-databases",
    name: "notion.databases",
    description: "Manage Notion databases",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "notion-blocks",
    name: "notion.blocks",
    description: "Manage Notion blocks",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "notion-search",
    name: "notion.search",
    description: "Search Notion content",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "notion-permissions",
    name: "notion.permissions",
    description: "Evaluate Notion permissions",
    version: "1.0.0",
    enabled: true,
  },
]

export const NotionCapability = {
  async getDefinitions(): Promise<ConnectorCapabilityDefinition[]> {
    return [...NotionCapabilityDefinitions]
  },

  async getDefinition(name: string): Promise<ConnectorCapabilityDefinition | undefined> {
    return NotionCapabilityDefinitions.find((d) => d.name === name)
  },
}