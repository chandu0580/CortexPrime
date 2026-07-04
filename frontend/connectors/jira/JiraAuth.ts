export type JiraAuthType = "api_token" | "oauth" | "pat"

export interface JiraAuthConfig {
  type: JiraAuthType
  site: string
  email?: string
  apiToken?: string
  token?: string
  clientId?: string
  clientSecret?: string
}

let authConfig: JiraAuthConfig | null = null

export const JiraAuth = {
  async configure(config: JiraAuthConfig): Promise<void> {
    authConfig = config
  },

  async getSite(): Promise<string | null> {
    return authConfig?.site ?? null
  },

  async getAuthType(): Promise<JiraAuthType | null> {
    return authConfig?.type ?? null
  },

  async getAuthHeaders(): Promise<Record<string, string>> {
    if (!authConfig) return {}
    const headers: Record<string, string> = {
      Accept: "application/json",
      "User-Agent": "CortexPrime-JiraConnector/1.0",
    }
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

  async getBaseUrl(): Promise<string> {
    const site = await this.getSite()
    return site ? `https://${site}.atlassian.net` : "https://your-domain.atlassian.net"
  },
}