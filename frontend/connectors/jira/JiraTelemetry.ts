interface ApiCallRecord {
  method: string; path: string; status: number; latencyMs: number; timestamp: string
}
interface FailureRecord {
  method: string; path: string; error: string; timestamp: string
}

const apiCalls: ApiCallRecord[] = []
const failures: FailureRecord[] = []

export const JiraTelemetry = {
  async recordApiCall(method: string, path: string, status: number, latencyMs: number): Promise<void> {
    apiCalls.push({ method, path, status, latencyMs, timestamp: new Date().toISOString() })
    if (apiCalls.length > 1000) apiCalls.shift()
  },
  async recordFailure(method: string, path: string, error: string): Promise<void> {
    failures.push({ method, path, error, timestamp: new Date().toISOString() })
    if (failures.length > 100) failures.shift()
  },
  async recordSuccess(_method: string, _path: string): Promise<void> {},
  async getMetrics(): Promise<{ totalCalls: number; totalFailures: number; successRate: number; averageLatencyMs: number }> {
    const totalCalls = apiCalls.length
    const totalFailures = failures.length
    const successRate = totalCalls > 0 ? Math.round(((totalCalls - totalFailures) / totalCalls) * 100) : 100
    const averageLatencyMs = totalCalls > 0 ? Math.round(apiCalls.reduce((s, c) => s + c.latencyMs, 0) / totalCalls) : 0
    return { totalCalls, totalFailures, successRate, averageLatencyMs }
  },
}