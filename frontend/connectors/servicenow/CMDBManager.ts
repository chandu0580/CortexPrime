import { ConfigurationItem, CMDBRelationship } from "./types"
import { ServiceNowClient } from "./ServiceNowClient"

function mapApiCi(api: Record<string, unknown>): ConfigurationItem {
  return {
    id: String(api.sys_id), instanceId: "", name: String(api.name ?? ""), sysClassName: String(api.sys_class_name ?? ""),
    serialNumber: String(api.serial_number ?? ""), assetTag: String(api.asset_tag ?? ""), category: String(api.category ?? ""),
    subcategory: String(api.subcategory ?? ""), status: (api.install_status as string ?? "1") === "1" ? "operational" : "non_operational",
    version: String(api.version ?? ""), location: String(api.location ?? ""), assignedTo: (api.assigned_to as Record<string, unknown>)?.value as string ?? null,
    operationalStatus: String(api.operational_status ?? ""), installDate: api.install_date as string ?? null,
    lastSeenAt: api.sys_updated_on as string ?? null, createdAt: String(api.sys_created_on ?? ""), updatedAt: String(api.sys_updated_on ?? ""),
  }
}

export const CMDBManager = {
  async registerConfigurationItem(name: string, sysClassName: string, category: string = "", subcategory: string = "", serialNumber: string = "", assetTag: string = "", version: string = "1.0", location: string = ""): Promise<ConfigurationItem | null> {
    const body = { name, sys_class_name: sysClassName, category, subcategory, serial_number: serialNumber, asset_tag: assetTag, version, location }
    const result = await ServiceNowClient.post<Record<string, unknown>>("/table/cmdb_ci", body)
    if (result.success && result.data?.result) return mapApiCi(result.data.result as Record<string, unknown>)
    return null
  },

  async updateConfigurationItem(id: string, updates: Record<string, unknown>): Promise<ConfigurationItem | null> {
    const result = await ServiceNowClient.patch<Record<string, unknown>>(`/table/cmdb_ci/${id}`, updates)
    if (result.success && result.data?.result) return mapApiCi(result.data.result as Record<string, unknown>)
    return null
  },

  async relateConfigurationItems(parentId: string, childId: string, type: string, direction: string = "contains"): Promise<CMDBRelationship | null> {
    const body = { parent: parentId, child: childId, type, direction }
    const result = await ServiceNowClient.post<Record<string, unknown>>("/table/cmdb_rel_ci", body)
    if (result.success && result.data?.result) {
      const r = result.data.result as Record<string, unknown>
      return { id: String(r.sys_id), instanceId: "", parentId, childId, type, direction, createdAt: String(r.sys_created_on ?? "") }
    }
    return null
  },

  async listConfigurationItems(): Promise<ConfigurationItem[]> {
    const result = await ServiceNowClient.get<Record<string, unknown>>("/table/cmdb_ci?sysparm_limit=100")
    if (result.success && result.data?.result) return (result.data.result as Record<string, unknown>[]).map(mapApiCi)
    return []
  },

  async retrieveConfigurationItem(id: string): Promise<ConfigurationItem | null> {
    const result = await ServiceNowClient.get<Record<string, unknown>>(`/table/cmdb_ci/${id}`)
    if (result.success && result.data?.result) return mapApiCi(result.data.result as Record<string, unknown>)
    return null
  },
}