export type ServiceNowAuthType = "basic" | "oauth" | "pat"

export interface ServiceNowAuthConfig {
  type: ServiceNowAuthType
  instance: string
  username?: string
  password?: string
  token?: string
  clientId?: string
  clientSecret?: string
}

let authConfig: ServiceNowAuthConfig | null = null

export const ServiceNowAuth = {
  async configure(config: ServiceNowAuthConfig): Promise<void> { authConfig = config },
  async getInstance(): Promise<string | null> { return authConfig?.instance ?? null },
  async getBaseUrl(): Promise<string> {
    const inst = await this.getInstance()
    return inst ? `https://${inst}.service-now.com/api/now` : "https://your-instance.service-now.com/api/now"
  },
  async getAuthHeaders(): Promise<Record<string, string>> {
    if (!authConfig) return {}
    const headers: Record<string, string> = { Accept: "application/json", "User-Agent": "CortexPrime-ServiceNowConnector/1.0" }
    if (authConfig.type === "basic" && authConfig.username && authConfig.password) {
      const encoded = Buffer.from(`${authConfig.username}:${authConfig.password}`).toString("base64")
      headers["Authorization"] = `Basic ${encoded}`
    } else if (authConfig.token) {
      headers["Authorization"] = `Bearer ${authConfig.token}`
    }
    return headers
  },
  async isAuthenticated(): Promise<boolean> {
    if (!authConfig) return false
    if (authConfig.type === "basic") return !!(authConfig.username && authConfig.password)
    return !!authConfig.token
  },
  async getAuthType(): Promise<ServiceNowAuthType | null> { return authConfig?.type ?? null },
}