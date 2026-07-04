const operations: DesktopOperationRecord[] = []
const failures: DesktopFailureRecord[] = []
const screenshots: DesktopScreenshotRecord[] = []
const sessions: DesktopSessionRecord[] = []
const applications: DesktopApplicationRecord[] = []

const MAX_OPS = 1000
const MAX_FAILURES = 100
const MAX_SCREENSHOTS = 500
const MAX_SESSIONS = 500
const MAX_APPS = 500

interface DesktopOperationRecord { action: string; latencyMs: number; success: boolean; timestamp: string }
interface DesktopFailureRecord { action: string; error: string; timestamp: string }
interface DesktopScreenshotRecord { id: string; format: string; monitorIndex: number | null; timestamp: string; sizeBytes: number | null }
interface DesktopSessionRecord { id: string; createdAt: string; closedAt: string | null; actionCount: number; errorCount: number }
interface DesktopApplicationRecord { name: string; action: "launched" | "closed" | "activated"; timestamp: string }

export const DesktopTelemetry = {
  async recordCall(action: string, latencyMs: number, success: boolean): Promise<void> {
    operations.push({ action, latencyMs, success, timestamp: new Date().toISOString() })
    if (operations.length > MAX_OPS) operations.shift()
  },

  async recordFailure(action: string, error: string): Promise<void> {
    failures.push({ action, error, timestamp: new Date().toISOString() })
    if (failures.length > MAX_FAILURES) failures.shift()
  },

  async recordScreenshot(screenshot: DesktopScreenshotRecord): Promise<void> {
    screenshots.push(screenshot)
    if (screenshots.length > MAX_SCREENSHOTS) screenshots.shift()
  },

  async recordSession(session: DesktopSessionRecord): Promise<void> {
    sessions.push(session)
    if (sessions.length > MAX_SESSIONS) sessions.shift()
  },

  async updateSession(sessionId: string, updates: Partial<DesktopSessionRecord>): Promise<void> {
    const session = sessions.find((s) => s.id === sessionId)
    if (session) Object.assign(session, updates)
  },

  async recordApplication(name: string, action: "launched" | "closed" | "activated"): Promise<void> {
    applications.push({ name, action, timestamp: new Date().toISOString() })
    if (applications.length > MAX_APPS) applications.shift()
  },

  async getMetrics(): Promise<{
    totalCalls: number; totalFailures: number; successRate: number
    averageLatencyMs: number; totalScreenshots: number; totalSessions: number
    activeSessions: number; actionBreakdown: Record<string, number>
    topApplications: Record<string, number>
  }> {
    const totalCalls = operations.length
    const totalFailures = failures.length
    const successRate = totalCalls > 0 ? Math.round(((totalCalls - totalFailures) / totalCalls) * 100) : 100
    const averageLatencyMs = totalCalls > 0 ? Math.round(operations.reduce((s, c) => s + c.latencyMs, 0) / totalCalls) : 0
    const actionBreakdown: Record<string, number> = {}
    for (const op of operations) actionBreakdown[op.action] = (actionBreakdown[op.action] ?? 0) + 1
    const topApplications: Record<string, number> = {}
    for (const app of applications) topApplications[app.name] = (topApplications[app.name] ?? 0) + 1
    return {
      totalCalls, totalFailures, successRate, averageLatencyMs,
      totalScreenshots: screenshots.length,
      totalSessions: sessions.length,
      activeSessions: sessions.filter((s) => s.closedAt === null).length,
      actionBreakdown, topApplications,
    }
  },

  async getCallHistory(limit?: number): Promise<DesktopOperationRecord[]> {
    return limit ? [...operations.slice(-limit)] : [...operations]
  },

  async getFailureHistory(limit?: number): Promise<DesktopFailureRecord[]> {
    return limit ? [...failures.slice(-limit)] : [...failures]
  },

  async getScreenshotHistory(limit?: number): Promise<DesktopScreenshotRecord[]> {
    return limit ? [...screenshots.slice(-limit)] : [...screenshots]
  },

  async clearHistory(): Promise<void> {
    operations.length = 0; failures.length = 0
    screenshots.length = 0; sessions.length = 0; applications.length = 0
  },
}