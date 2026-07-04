import { PlaywrightManager } from "./PlaywrightManager"
import { BrowserSessionManager } from "./BrowserSessionManager"
import { BrowserTelemetry } from "./BrowserTelemetry"

export interface BrowserHealthStatus {
  browserProcessAlive: boolean
  memoryUsageMb: number | null
  activeSessions: number
  pageCount: number
  contextCount: number
  browserCount: number
  crashCount: number
  lastHealthCheck: string
  uptime: number
}

export interface BrowserMetrics {
  totalSessions: number
  activeSessions: number
  totalPages: number
  totalActions: number
  totalDownloads: number
  totalUploads: number
  totalScreenshots: number
  totalPdfs: number
  totalNavigations: number
  totalExtractions: number
  averageActionLatencyMs: number
  successRate: number
}

let crashCount = 0
let startTime = Date.now()

export const BrowserHealthTracker = {
  async getHealthStatus(): Promise<BrowserHealthStatus> {
    const pageCount = await PlaywrightManager.getPageCount()
    const contextCount = await PlaywrightManager.getContextCount()
    const browserCount = await PlaywrightManager.getBrowserCount()
    const activeSessions = (await BrowserSessionManager.getActiveSessions()).length

    let memoryUsageMb: number | null = null
    if (typeof process !== "undefined" && process.memoryUsage) {
      const memUsage = process.memoryUsage()
      memoryUsageMb = Math.round(memUsage.heapUsed / 1024 / 1024)
    }

    return {
      browserProcessAlive: browserCount > 0,
      memoryUsageMb,
      activeSessions,
      pageCount,
      contextCount,
      browserCount,
      crashCount,
      lastHealthCheck: new Date().toISOString(),
      uptime: Date.now() - startTime,
    }
  },

  async getMetrics(): Promise<BrowserMetrics> {
    const telemetryMetrics = await BrowserTelemetry.getMetrics()
    const activeSessions = (await BrowserSessionManager.getActiveSessions()).length
    const sessionHistory = await BrowserTelemetry.getSessionHistory()

    return {
      totalSessions: sessionHistory.length,
      activeSessions,
      totalPages: await PlaywrightManager.getPageCount(),
      totalActions: telemetryMetrics.totalCalls,
      totalDownloads: telemetryMetrics.totalDownloads,
      totalUploads: telemetryMetrics.totalUploads,
      totalScreenshots: telemetryMetrics.totalScreenshots,
      totalPdfs: telemetryMetrics.totalPdfs,
      totalNavigations: telemetryMetrics.actionBreakdown["navigate"] ?? 0,
      totalExtractions: telemetryMetrics.actionBreakdown["extract"] ?? 0,
      averageActionLatencyMs: telemetryMetrics.averageLatencyMs,
      successRate: telemetryMetrics.successRate,
    }
  },

  recordCrash(): void {
    crashCount++
  },

  resetStartTime(): void {
    startTime = Date.now()
  },

  getCrashCount(): number {
    return crashCount
  },

  resetCrashCount(): void {
    crashCount = 0
  },
}
