export type SlackAuthType = "bot" | "user" | "oauth"

export interface SlackAuthConfig {
  type: SlackAuthType
  botToken?: string
  userToken?: string
  clientId?: string
  clientSecret?: string
}

let authConfig: SlackAuthConfig | null = null

export const SlackAuth = {
  async configure(config: SlackAuthConfig): Promise<void> {
    authConfig = config
  },

  async getToken(): Promise<string | null> {
    if (!authConfig) return null
    if (authConfig.type === "bot" && authConfig.botToken) return authConfig.botToken
    if (authConfig.type === "user" && authConfig.userToken) return authConfig.userToken
    return authConfig.botToken ?? authConfig.userToken ?? null
  },

  async getAuthType(): Promise<SlackAuthType | null> {
    return authConfig?.type ?? null
  },

  async getAuthHeaders(): Promise<Record<string, string>> {
    const token = await this.getToken()
    if (!token) return {}
    return { Authorization: `Bearer ${token}`, "Content-Type": "application/json", "User-Agent": "CortexPrime-SlackConnector/1.0" }
  },

  async isAuthenticated(): Promise<boolean> {
    return (await this.getToken()) !== null
  },
}