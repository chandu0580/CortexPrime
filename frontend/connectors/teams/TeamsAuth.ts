export type TeamsAuthType = "client_credentials" | "auth_code" | "managed_identity"

export interface TeamsAuthConfig {
  type: TeamsAuthType
  tenantId: string
  clientId?: string
  clientSecret?: string
  token?: string
}

let authConfig: TeamsAuthConfig | null = null
let cachedToken: string | null = null

export const TeamsAuth = {
  async configure(config: TeamsAuthConfig): Promise<void> {
    authConfig = config
    cachedToken = null
  },

  async getAuthType(): Promise<TeamsAuthType | null> {
    return authConfig?.type ?? null
  },

  async getTenantId(): Promise<string | null> {
    return authConfig?.tenantId ?? null
  },

  async getToken(): Promise<string | null> {
    if (cachedToken) return cachedToken
    if (!authConfig) return null
    if (authConfig.token) {
      cachedToken = authConfig.token
      return cachedToken
    }
    if (authConfig.type === "client_credentials" && authConfig.clientId && authConfig.clientSecret) {
      const url = `https://login.microsoftonline.com/${authConfig.tenantId}/oauth2/v2.0/token`
      const body = new URLSearchParams({
        client_id: authConfig.clientId,
        client_secret: authConfig.clientSecret,
        scope: "https://graph.microsoft.com/.default",
        grant_type: "client_credentials",
      })
      try {
        const response = await fetch(url, { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body })
        const data = await response.json() as Record<string, unknown>
        cachedToken = data.access_token as string ?? null
        return cachedToken
      } catch {
        return null
      }
    }
    return null
  },

  async getAuthHeaders(): Promise<Record<string, string>> {
    const token = await this.getToken()
    if (!token) return {}
    return { Authorization: `Bearer ${token}`, "Content-Type": "application/json", "User-Agent": "CortexPrime-TeamsConnector/1.0" }
  },

  async isAuthenticated(): Promise<boolean> {
    return (await this.getToken()) !== null
  },
}