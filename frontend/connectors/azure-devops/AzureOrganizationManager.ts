import { AzureOrganization } from "./types"
import { AzureDevOpsClient } from "./AzureDevOpsClient"
import { AzureDevOpsAuth } from "./AzureDevOpsAuth"

function mapApiOrg(api: Record<string, unknown>): AzureOrganization {
  return {
    id: String(api.id), name: String(api.accountName ?? api.name ?? ""),
    displayName: String(api.displayName ?? api.name ?? ""), description: String(api.description ?? ""),
    projects: [], archived: false, createdAt: "", updatedAt: "",
  }
}

export const AzureOrganizationManager = {
  async getOrganization(): Promise<AzureOrganization | null> {
    const orgName = await AzureDevOpsAuth.getOrganization()
    if (!orgName) return null
    return { id: orgName, name: orgName, displayName: orgName, description: "", projects: [], archived: false, createdAt: "", updatedAt: "" }
  },

  async listOrganizations(): Promise<AzureOrganization[]> {
    const org = await this.getOrganization()
    return org ? [org] : []
  },
}