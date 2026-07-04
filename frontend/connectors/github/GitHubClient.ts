import { GitHubAuth } from "./GitHubAuth"
import { GitHubTelemetry } from "./GitHubTelemetry"
import { cortexEventBus } from "@/event-bus/cortexEventBus"

const GITHUB_API = "https://api.github.com"
const MAX_RETRIES = 3
const INITIAL_BACKOFF = 1000

interface GitHubApiResponse<T> {
  success: boolean
  data: T | null
  status: number
  headers: Record<string, string>
  error: string | null
}

export const GitHubClient = {
  async request<T>(
    method: string,
    path: string,
    body?: Record<string, unknown>,
    isGraphQL: boolean = false,
  ): Promise<GitHubApiResponse<T>> {
    const startTime = Date.now()
    const baseUrl = isGraphQL ? GITHUB_API : GITHUB_API
    const url = isGraphQL ? `${baseUrl}/graphql` : `${baseUrl}${path}`
    const headers = await GitHubAuth.getAuthHeaders()
    let lastError: string | null = null
    let lastStatus = 0
    let lastHeaders: Record<string, string> = {}

    for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
      try {
        const options: RequestInit = {
          method,
          headers: {
            ...headers,
            "Content-Type": "application/json",
          },
        }

        if (isGraphQL && body) {
          options.body = JSON.stringify({ query: body.query, variables: body.variables })
        } else if (body && method !== "GET") {
          options.body = JSON.stringify(body)
        }

        const response = await fetch(url, options)
        lastStatus = response.status
        response.headers.forEach((value, key) => { lastHeaders[key] = value })

        const rateLimitRemaining = parseInt(response.headers.get("x-ratelimit-remaining") ?? "0", 10)
        const rateLimitReset = parseInt(response.headers.get("x-ratelimit-reset") ?? "0", 10)

        const latencyMs = Date.now() - startTime
        await GitHubTelemetry.recordApiCall(method, path, lastStatus, latencyMs)
        await cortexEventBus.publish("github", "connector", "github.api.call", "GitHubClient", {
          method, path, status: lastStatus, latencyMs, attempt,
        })

        if (response.status === 429 || response.status === 403) {
          const retryAfter = parseInt(response.headers.get("retry-after") ?? "60", 10)
          await new Promise((resolve) => setTimeout(resolve, retryAfter * 1000))
          continue
        }

        if (!response.ok) {
          const errorBody = await response.text()
          lastError = `GitHub API error ${response.status}: ${errorBody}`
          await GitHubTelemetry.recordFailure(method, path, lastError)
          continue
        }

        const data = await response.json() as T
        await GitHubTelemetry.recordSuccess(method, path)

        return { success: true, data, status: response.status, headers: lastHeaders, error: null }
      } catch (err) {
        lastError = err instanceof Error ? err.message : String(err)
        if (attempt < MAX_RETRIES - 1) {
          await new Promise((resolve) => setTimeout(resolve, INITIAL_BACKOFF * Math.pow(2, attempt)))
        }
      }
    }

    await GitHubTelemetry.recordFailure(method, path, lastError ?? "unknown")
    return { success: false, data: null, status: lastStatus, headers: lastHeaders, error: lastError }
  },

  async get<T>(path: string): Promise<GitHubApiResponse<T>> {
    return this.request<T>("GET", path)
  },

  async post<T>(path: string, body?: Record<string, unknown>): Promise<GitHubApiResponse<T>> {
    return this.request<T>("POST", path, body)
  },

  async patch<T>(path: string, body?: Record<string, unknown>): Promise<GitHubApiResponse<T>> {
    return this.request<T>("PATCH", path, body)
  },

  async put<T>(path: string, body?: Record<string, unknown>): Promise<GitHubApiResponse<T>> {
    return this.request<T>("PUT", path, body)
  },

  async delete<T>(path: string): Promise<GitHubApiResponse<T>> {
    return this.request<T>("DELETE", path)
  },

  async graphql<T>(query: string, variables?: Record<string, unknown>): Promise<GitHubApiResponse<T>> {
    return this.request<T>("POST", "", { query, variables } as unknown as Record<string, unknown>, true)
  },
}