import { ConfluenceAuth } from "./ConfluenceAuth"
import { ConfluenceTelemetry } from "./ConfluenceTelemetry"
import { cortexEventBus } from "@/event-bus/cortexEventBus"

const MAX_RETRIES = 3
const INITIAL_BACKOFF = 1000

interface ConfluenceApiResponse<T> {
  success: boolean; data: T | null; status: number; error: string | null
}

export const ConfluenceClient = {
  async request<T>(method: string, path: string, body?: Record<string, unknown>): Promise<ConfluenceApiResponse<T>> {
    const startTime = Date.now()
    const baseUrl = await ConfluenceAuth.getBaseUrl()
    const url = `${baseUrl}${path}`
    const headers = await ConfluenceAuth.getAuthHeaders()
    let lastError: string | null = null; let lastStatus = 0

    for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
      try {
        const options: RequestInit = { method, headers: { ...headers, "Content-Type": "application/json" } }
        if (body && method !== "GET") options.body = JSON.stringify(body)
        const response = await fetch(url, options)
        lastStatus = response.status
        const latencyMs = Date.now() - startTime
        await ConfluenceTelemetry.recordApiCall(method, path, lastStatus, latencyMs)
        await cortexEventBus.publish("confluence", "connector", "confluence.api.call", "ConfluenceClient", { method, path, status: lastStatus, latencyMs, attempt })

        if (response.status === 429) {
          const retryAfter = parseInt(response.headers.get("retry-after") ?? "30", 10)
          await new Promise((resolve) => setTimeout(resolve, retryAfter * 1000)); continue
        }
        if (!response.ok) {
          const errorBody = await response.text()
          lastError = `Confluence API error ${response.status}: ${errorBody}`
          await ConfluenceTelemetry.recordFailure(method, path, lastError); continue
        }
        if (response.status === 204) return { success: true, data: null as T, status: 204, error: null }
        const data = await response.json() as T
        await ConfluenceTelemetry.recordSuccess(method, path)
        return { success: true, data, status: response.status, error: null }
      } catch (err) {
        lastError = err instanceof Error ? err.message : String(err)
        if (attempt < MAX_RETRIES - 1) await new Promise((resolve) => setTimeout(resolve, INITIAL_BACKOFF * Math.pow(2, attempt)))
      }
    }
    await ConfluenceTelemetry.recordFailure(method, path, lastError ?? "unknown")
    return { success: false, data: null, status: lastStatus, error: lastError }
  },

  async get<T>(path: string): Promise<ConfluenceApiResponse<T>> { return this.request<T>("GET", path) },
  async post<T>(path: string, body?: Record<string, unknown>): Promise<ConfluenceApiResponse<T>> { return this.request<T>("POST", path, body) },
  async put<T>(path: string, body?: Record<string, unknown>): Promise<ConfluenceApiResponse<T>> { return this.request<T>("PUT", path, body) },
  async delete<T>(path: string): Promise<ConfluenceApiResponse<T>> { return this.request<T>("DELETE", path) },
}