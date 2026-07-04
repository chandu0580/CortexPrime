import { ConnectorCapabilityDefinition } from "../../connector-framework/types"

export const ServiceNowCapabilityDefinitions: ConnectorCapabilityDefinition[] = [
  {
    id: "servicenow-incidents",
    name: "servicenow.incidents",
    description: "Manage ServiceNow incidents",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "servicenow-changes",
    name: "servicenow.changes",
    description: "Manage ServiceNow change requests",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "servicenow-cmdb",
    name: "servicenow.cmdb",
    description: "Manage ServiceNow CMDB",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "servicenow-knowledge",
    name: "servicenow.knowledge",
    description: "Manage ServiceNow knowledge base",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "servicenow-catalog",
    name: "servicenow.catalog",
    description: "Manage ServiceNow service catalog",
    version: "1.0.0",
    enabled: true,
  },
  {
    id: "servicenow-permissions",
    name: "servicenow.permissions",
    description: "Evaluate ServiceNow permissions",
    version: "1.0.0",
    enabled: true,
  },
]

export const ServiceNowCapability = {
  async getDefinitions(): Promise<ConnectorCapabilityDefinition[]> {
    return [...ServiceNowCapabilityDefinitions]
  },

  async getDefinition(name: string): Promise<ConnectorCapabilityDefinition | undefined> {
    return ServiceNowCapabilityDefinitions.find((d) => d.name === name)
  },
}