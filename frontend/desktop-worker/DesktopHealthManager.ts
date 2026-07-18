import { DesktopSessionManager } from "./DesktopSessionManager"
import { DesktopTelemetry } from "./DesktopTelemetry"
import type { DesktopHealthStatus, DesktopHealthStatusResult } from "./types"

const startedAt = Date.now()
let consecutiveErrors = 0

export const DesktopHealthManager = {
  getHealth(): DesktopHealthStatusResult {
    const sessionHealth = DesktopSessionManager.getHealthStatus()
    const metrics = DesktopTelemetry.getMetrics()
    let status: DesktopHealthStatus = "idle"

    if (sessionHealth.sessions.active > 0) status = "busy"
    else if (consecutiveErrors > 3) status = "recovering"
    else if (sessionHealth.sessions.total > 0) status = "running"

    return {
      status,
      sessions: sessionHealth.sessions,
      lastAction: sessionHealth.lastAction,
      lastActionAt: sessionHealth.lastActionAt,
      uptimeMs: Date.now() - startedAt,
      consecutiveFailures: consecutiveErrors,
    }
  },

  recordError(): void { consecutiveErrors++ },

  recordSuccess(): void { consecutiveErrors = Math.max(0, consecutiveErrors - 1) },

  isHealthy(): boolean {
    return consecutiveErrors < 5
  },

  getUptimeMs(): number {
    return Date.now() - startedAt
  },
}