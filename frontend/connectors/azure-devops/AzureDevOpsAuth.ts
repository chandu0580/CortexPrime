export type AzureDevOpsAuthType = "pat" | "oauth" | "managed_identity"

export interface AzureDevOpsAuthConfig {
  type: AzureDevOpsAuthType
  organization: string
  pat?: string
  token?: string
}

let authConfig: AzureDevOpsAuthConfig | null = null

export const AzureDevOpsAuth = {
  async configure(config: AzureDevOpsAuthConfig): Promise<void> { authConfig = config },

  async getOrganization(): Promise<string | null> { return authConfig?.organization ?? null },

  async getBaseUrl(): Promise<string> {
    const org = await this.getOrganization()
    return org ? `https://dev.azure.com/${org}` : "https://dev.azure.com/your-organization"
  },

  async getAuthHeaders(): Promise<Record<string, string>> {
    if (!authConfig) return {}
    const headers: Record<string, string> = { Accept: "application/json", "User-Agent": "CortexPrime-AzureDevOpsConnector/1.0" }
    const pat = authConfig.pat ?? authConfig.token
    if (pat) {
      const encoded = Buffer.from(`:${pat}`).toString("base64")
      headers["Authorization"] = `Basic ${encoded}`
    }
    return headers
  },

  async isAuthenticated(): Promise<boolean> { return !!(authConfig?.pat ?? authConfig?.token) },
  async getAuthType(): Promise<AzureDevOpsAuthType | null> { return authConfig?.type ?? null },
}