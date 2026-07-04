import { SlackAuth } from "./SlackAuth"
import { SlackTelemetry } from "./SlackTelemetry"
import { cortexEventBus } from "@/event-bus/cortexEventBus"

const MAX_RETRIES = 3
const INITIAL_BACKOFF = 1000

interface SlackApiResponse<T> {
  success: boolean
  data: T | null
  status: number
  error: string | null
}

const SLACK_API = "https://slack.com/api"

export const SlackClient = {
  async request<T>(method: string, path: string, body?: Record<string, unknown>): Promise<SlackApiResponse<T>> {
    const startTime = Date.now()
    const url = `${SLACK_API}${path}`
    const headers = await SlackAuth.getAuthHeaders()
    let lastError: string | null = null
    let lastStatus = 0

    for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
      try {
        const options: RequestInit = { method, headers: { ...headers, "Content-Type": "application/json" } }
        if (body && method !== "GET") options.body = JSON.stringify(body)

        const response = await fetch(url, options)
        lastStatus = response.status
        const latencyMs = Date.now() - startTime

        await SlackTelemetry.recordApiCall(method, path, lastStatus, latencyMs)
        await cortexEventBus.publish("slack", "connector", "slack.api.call", "SlackClient", { method, path, status: lastStatus, latencyMs, attempt })

        if (response.status === 429) {
          const retryAfter = parseInt(response.headers.get("retry-after") ?? "30", 10)
          await new Promise((resolve) => setTimeout(resolve, retryAfter * 1000))
          continue
        }

        const data = await response.json() as Record<string, unknown>
        if (!response.ok || data.ok === false) {
          lastError = `Slack API error: ${data.error ?? response.statusText}`
          await SlackTelemetry.recordFailure(method, path, lastError)
          if (data.error === "rate_limited") {
            const retryAfter = Number(data.retry_after ?? "30") * 1000
            await new Promise((resolve) => setTimeout(resolve, retryAfter))
            continue
          }
          return { success: false, data: null, status: response.status, error: lastError }
        }

        await SlackTelemetry.recordSuccess(method, path)
        return { success: true, data: data as T, status: response.status, error: null }
      } catch (err) {
        lastError = err instanceof Error ? err.message : String(err)
        if (attempt < MAX_RETRIES - 1) await new Promise((resolve) => setTimeout(resolve, INITIAL_BACKOFF * Math.pow(2, attempt)))
      }
    }

    await SlackTelemetry.recordFailure(method, path, lastError ?? "unknown")
    return { success: false, data: null, status: lastStatus, error: lastError }
  },

  async get<T>(path: string): Promise<SlackApiResponse<T>> { return this.request<T>("GET", path) },
  async post<T>(path: string, body?: Record<string, unknown>): Promise<SlackApiResponse<T>> { return this.request<T>("POST", path, body) },
}