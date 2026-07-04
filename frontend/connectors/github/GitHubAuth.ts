export type GitHubAuthType = "pat" | "github_app" | "oauth"

export interface GitHubAuthConfig {
  type: GitHubAuthType
  token?: string
  appId?: string
  privateKey?: string
  installationId?: string
  clientId?: string
  clientSecret?: string
}

let authConfig: GitHubAuthConfig | null = null

export const GitHubAuth = {
  async configure(config: GitHubAuthConfig): Promise<void> {
    authConfig = config
  },

  async getToken(): Promise<string | null> {
    if (!authConfig) return null
    if (authConfig.type === "pat" && authConfig.token) return authConfig.token
    if (authConfig.type === "oauth" && authConfig.token) return authConfig.token
    if (authConfig.type === "github_app" && authConfig.token) return authConfig.token
    return null
  },

  async getAuthType(): Promise<GitHubAuthType | null> {
    return authConfig?.type ?? null
  },

  async getAuthHeaders(): Promise<Record<string, string>> {
    const token = await this.getToken()
    if (!token) return {}
    return {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github.v3+json",
      "User-Agent": "CortexPrime-GitHubConnector/1.0",
    }
  },

  async isAuthenticated(): Promise<boolean> {
    return (await this.getToken()) !== null
  },
}