import { AzureDevOpsAuth } from "./AzureDevOpsAuth"
import { AzureDevOpsTelemetry } from "./AzureDevOpsTelemetry"
import { cortexEventBus } from "@/event-bus/cortexEventBus"

const MAX_RETRIES = 3; const INITIAL_BACKOFF = 1000

interface AzureDevOpsApiResponse<T> { success: boolean; data: T | null; status: number; error: string | null }

export const AzureDevOpsClient = {
  async request<T>(method: string, path: string, body?: unknown, apiVersion: string = "7.0"): Promise<AzureDevOpsApiResponse<T>> {
    const startTime = Date.now()
    const baseUrl = await AzureDevOpsAuth.getBaseUrl()
    const sep = path.includes("?") ? "&" : "?"
    const url = `${baseUrl}${path}${sep}api-version=${apiVersion}`
    const headers = await AzureDevOpsAuth.getAuthHeaders()
    let lastError: string | null = null; let lastStatus = 0

    for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
      try {
        const options: RequestInit = { method, headers: { ...headers, "Content-Type": "application/json" } }
        if (body && method !== "GET") options.body = JSON.stringify(body)
        const response = await fetch(url, options)
        lastStatus = response.status
        const latencyMs = Date.now() - startTime
        await AzureDevOpsTelemetry.recordApiCall(method, path, lastStatus, latencyMs)
        await cortexEventBus.publish("azure", "connector", "azure.api.call", "AzureDevOpsClient", { method, path, status: lastStatus, latencyMs, attempt })

        if (response.status === 429) {
          const retryAfter = parseInt(response.headers.get("retry-after") ?? "30", 10)
          await new Promise((resolve) => setTimeout(resolve, retryAfter * 1000)); continue
        }
        if (!response.ok) {
          const errorBody = await response.text()
          lastError = `Azure DevOps API error ${response.status}: ${errorBody}`
          await AzureDevOpsTelemetry.recordFailure(method, path, lastError); continue
        }
        if (response.status === 204) return { success: true, data: null as T, status: 204, error: null }
        const data = await response.json() as T
        await AzureDevOpsTelemetry.recordSuccess(method, path)
        return { success: true, data, status: response.status, error: null }
      } catch (err) {
        lastError = err instanceof Error ? err.message : String(err)
        if (attempt < MAX_RETRIES - 1) await new Promise((resolve) => setTimeout(resolve, INITIAL_BACKOFF * Math.pow(2, attempt)))
      }
    }
    await AzureDevOpsTelemetry.recordFailure(method, path, lastError ?? "unknown")
    return { success: false, data: null, status: lastStatus, error: lastError }
  },

  async get<T>(path: string): Promise<AzureDevOpsApiResponse<T>> { return this.request<T>("GET", path) },
  async post<T>(path: string, body?: unknown): Promise<AzureDevOpsApiResponse<T>> { return this.request<T>("POST", path, body) },
  async patch<T>(path: string, body?: unknown): Promise<AzureDevOpsApiResponse<T>> { return this.request<T>("PATCH", path, body) },
  async delete<T>(path: string): Promise<AzureDevOpsApiResponse<T>> { return this.request<T>("DELETE", path) },
}