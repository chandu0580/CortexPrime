import { TeamsOrganization } from "./types"
import { TeamsClient } from "./TeamsClient"

function mapApiOrg(api: Record<string, unknown>): TeamsOrganization {
  return {
    id: String(api.id),
    name: String(api.id ?? ""),
    displayName: String(api.displayName ?? ""),
    description: String(api.description ?? ""),
    tenantId: String(api.tenantId ?? api.id ?? ""),
    teams: [], archived: false,
    createdAt: "", updatedAt: "",
  }
}

export const TeamsOrganizationManager = {
  async getOrganization(): Promise<TeamsOrganization | null> {
    const result = await TeamsClient.get<Record<string, unknown>>("/organization")
    if (result.success && result.data?.value) {
      const orgs = result.data.value as Record<string, unknown>[]
      if (orgs.length > 0) return mapApiOrg(orgs[0])
    }
    return null
  },

  async listOrganizations(): Promise<TeamsOrganization[]> {
    const result = await TeamsClient.get<Record<string, unknown>>("/organization")
    if (result.success && result.data?.value) {
      return (result.data.value as Record<string, unknown>[]).map(mapApiOrg)
    }
    return []
  },

  async getOrganizationUsers(): Promise<Record<string, unknown>[]> {
    const result = await TeamsClient.get<Record<string, unknown>>("/users?$top=200")
    if (result.success && result.data?.value) return result.data.value as Record<string, unknown>[]
    return []
  },
}