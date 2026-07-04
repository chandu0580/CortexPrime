import { ServiceNowAuth } from "./ServiceNowAuth"
import { ServiceNowTelemetry } from "./ServiceNowTelemetry"
import { cortexEventBus } from "@/event-bus/cortexEventBus"

const MAX_RETRIES = 3; const INITIAL_BACKOFF = 1000

interface ServiceNowApiResponse<T> { success: boolean; data: T | null; status: number; error: string | null }

export const ServiceNowClient = {
  async request<T>(method: string, path: string, body?: Record<string, unknown>): Promise<ServiceNowApiResponse<T>> {
    const startTime = Date.now()
    const baseUrl = await ServiceNowAuth.getBaseUrl()
    const url = `${baseUrl}${path}`
    const headers = await ServiceNowAuth.getAuthHeaders()
    let lastError: string | null = null; let lastStatus = 0

    for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
      try {
        const options: RequestInit = { method, headers: { ...headers, "Content-Type": "application/json" } }
        if (body && method !== "GET") options.body = JSON.stringify(body)
        const response = await fetch(url, options)
        lastStatus = response.status
        const latencyMs = Date.now() - startTime
        await ServiceNowTelemetry.recordApiCall(method, path, lastStatus, latencyMs)
        await cortexEventBus.publish("servicenow", "connector", "servicenow.api.call", "ServiceNowClient", { method, path, status: lastStatus, latencyMs, attempt })

        if (!response.ok) {
          const errorBody = await response.text()
          lastError = `ServiceNow API error ${response.status}: ${errorBody}`
          await ServiceNowTelemetry.recordFailure(method, path, lastError); continue
        }
        if (response.status === 204) return { success: true, data: null as T, status: 204, error: null }
        const data = await response.json() as T
        await ServiceNowTelemetry.recordSuccess(method, path)
        return { success: true, data, status: response.status, error: null }
      } catch (err) {
        lastError = err instanceof Error ? err.message : String(err)
        if (attempt < MAX_RETRIES - 1) await new Promise((resolve) => setTimeout(resolve, INITIAL_BACKOFF * Math.pow(2, attempt)))
      }
    }
    await ServiceNowTelemetry.recordFailure(method, path, lastError ?? "unknown")
    return { success: false, data: null, status: lastStatus, error: lastError }
  },

  async get<T>(path: string): Promise<ServiceNowApiResponse<T>> { return this.request<T>("GET", path) },
  async post<T>(path: string, body?: Record<string, unknown>): Promise<ServiceNowApiResponse<T>> { return this.request<T>("POST", path, body) },
  async patch<T>(path: string, body?: Record<string, unknown>): Promise<ServiceNowApiResponse<T>> { return this.request<T>("PATCH", path, body) },
  async delete<T>(path: string): Promise<ServiceNowApiResponse<T>> { return this.request<T>("DELETE", path) },
}