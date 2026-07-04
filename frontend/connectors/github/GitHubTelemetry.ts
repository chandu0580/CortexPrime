interface ApiCallRecord {
  method: string
  path: string
  status: number
  latencyMs: number
  timestamp: string
}

interface FailureRecord {
  method: string
  path: string
  error: string
  timestamp: string
}

const apiCalls: ApiCallRecord[] = []
const failures: FailureRecord[] = []
let rateLimitRemaining = 0
let rateLimitReset = 0

export const GitHubTelemetry = {
  async recordApiCall(method: string, path: string, status: number, latencyMs: number): Promise<void> {
    apiCalls.push({ method, path, status, latencyMs, timestamp: new Date().toISOString() })
    if (apiCalls.length > 1000) apiCalls.shift()
  },

  async recordFailure(method: string, path: string, error: string): Promise<void> {
    failures.push({ method, path, error, timestamp: new Date().toISOString() })
    if (failures.length > 100) failures.shift()
  },

  async recordSuccess(method: string, path: string): Promise<void> {
  },

  async updateRateLimit(remaining: number, reset: number): Promise<void> {
    rateLimitRemaining = remaining
    rateLimitReset = reset
  },

  async getMetrics(): Promise<{ totalCalls: number; totalFailures: number; successRate: number; averageLatencyMs: number; rateLimitRemaining: number }> {
    const totalCalls = apiCalls.length
    const totalFailures = failures.length
    const successRate = totalCalls > 0 ? Math.round(((totalCalls - totalFailures) / totalCalls) * 100) : 100
    const averageLatencyMs = totalCalls > 0 ? Math.round(apiCalls.reduce((s, c) => s + c.latencyMs, 0) / totalCalls) : 0

    return { totalCalls, totalFailures, successRate, averageLatencyMs, rateLimitRemaining }
  },

  async getRecentCalls(count: number = 10): Promise<ApiCallRecord[]> {
    return apiCalls.slice(-count)
  },
}