export type NotionAuthType = "internal_integration" | "oauth"

export interface NotionAuthConfig {
  type: NotionAuthType
  token: string
  clientId?: string
  clientSecret?: string
}

let authConfig: NotionAuthConfig | null = null

export const NotionAuth = {
  async configure(config: NotionAuthConfig): Promise<void> { authConfig = config },
  async getToken(): Promise<string | null> { return authConfig?.token ?? null },
  async getAuthType(): Promise<NotionAuthType | null> { return authConfig?.type ?? null },
  async getAuthHeaders(): Promise<Record<string, string>> {
    const token = await this.getToken()
    if (!token) return {}
    return { Authorization: `Bearer ${token}`, "Content-Type": "application/json", "Notion-Version": "2022-06-28", "User-Agent": "CortexPrime-NotionConnector/1.0" }
  },
  async isAuthenticated(): Promise<boolean> { return !!(await this.getToken()) },
}