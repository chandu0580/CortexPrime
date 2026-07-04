export type ConfluenceAuthType = "api_token" | "oauth" | "pat"

export interface ConfluenceAuthConfig {
  type: ConfluenceAuthType
  site: string
  email?: string
  apiToken?: string
  token?: string
}

let authConfig: ConfluenceAuthConfig | null = null

export const ConfluenceAuth = {
  async configure(config: ConfluenceAuthConfig): Promise<void> {
    authConfig = config
  },

  async getSite(): Promise<string | null> {
    return authConfig?.site ?? null
  },

  async getBaseUrl(): Promise<string> {
    const site = await this.getSite()
    return site ? `https://${site}.atlassian.net/wiki/api/v2` : "https://your-domain.atlassian.net/wiki/api/v2"
  },

  async getAuthType(): Promise<ConfluenceAuthType | null> { return authConfig?.type ?? null },

  async getAuthHeaders(): Promise<Record<string, string>> {
    if (!authConfig) return {}
    const headers: Record<string, string> = { Accept: "application/json", "User-Agent": "CortexPrime-ConfluenceConnector/1.0" }
    if (authConfig.type === "api_token" && authConfig.email && authConfig.apiToken) {
      const encoded = Buffer.from(`${authConfig.email}:${authConfig.apiToken}`).toString("base64")
      headers["Authorization"] = `Basic ${encoded}`
    } else if (authConfig.token) {
      headers["Authorization"] = `Bearer ${authConfig.token}`
    }
    return headers
  },

  async isAuthenticated(): Promise<boolean> {
    const headers = await this.getAuthHeaders()
    return "Authorization" in headers
  },
}