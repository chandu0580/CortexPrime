export type IntelligenceHealthStatus = "healthy" | "degraded" | "unhealthy" | "unknown"

export interface IntelligenceHealthReport {
  workerId: string
  status: IntelligenceHealthStatus
  sessionCount: number
  consecutiveFailures: number
  pipelineFailures: number
  stalledExecutions: number
  recoveryReady: boolean
  message: string
  timestamp: string
}

const healthStates = new Map<string, {
  consecutiveFailures: number
  pipelineFailures: number
  totalErrors: number
  lastActivityAt: string | null
  stalledSince: string | null
}>()

export const IntelligenceHealthManager = {
  async initialize(workerId: string): Promise<void> {
    if (healthStates.has(workerId)) return
    healthStates.set(workerId, {
      consecutiveFailures: 0,
      pipelineFailures: 0,
      totalErrors: 0,
      lastActivityAt: null,
      stalledSince: null,
    })
  },

  async recordSuccess(workerId: string): Promise<void> {
    const state = healthStates.get(workerId)
    if (state) {
      state.consecutiveFailures = 0
      state.lastActivityAt = new Date().toISOString()
      state.stalledSince = null
    }
  },

  async recordFailure(workerId: string): Promise<void> {
    const state = healthStates.get(workerId)
    if (state) {
      state.consecutiveFailures++
      state.totalErrors++
      state.lastActivityAt = new Date().toISOString()
    }
  },

  async recordPipelineFailure(workerId: string): Promise<void> {
    const state = healthStates.get(workerId)
    if (state) {
      state.pipelineFailures++
      state.totalErrors++
      state.lastActivityAt = new Date().toISOString()
    }
  },

  async checkStalledExecution(workerId: string): Promise<boolean> {
    const state = healthStates.get(workerId)
    if (!state || !state.lastActivityAt) return false

    const elapsed = Date.now() - new Date(state.lastActivityAt).getTime()
    const stalled = elapsed > 120_000

    if (stalled && !state.stalledSince) {
      state.stalledSince = new Date().toISOString()
    } else if (!stalled) {
      state.stalledSince = null
    }

    return stalled
  },

  async check(workerId: string): Promise<IntelligenceHealthReport> {
    const state = healthStates.get(workerId)
    if (!state) {
      return {
        workerId,
        status: "unknown",
        sessionCount: 0,
        consecutiveFailures: 0,
        pipelineFailures: 0,
        stalledExecutions: 0,
        recoveryReady: false,
        message: "Health state not initialized",
        timestamp: new Date().toISOString(),
      }
    }

    const stalled = await this.checkStalledExecution(workerId)
    const { IntelligenceSessionManager } = await import("./IntelligenceSessionManager")
    const sessions = await IntelligenceSessionManager.getActiveSessions()

    let status: IntelligenceHealthStatus = "healthy"
    let message = "Intelligence worker is operating normally"
    let recoveryReady = false

    if (state.consecutiveFailures >= 10) {
      status = "unhealthy"
      message = `Intelligence worker has ${state.consecutiveFailures} consecutive failures, requires intervention`
    } else if (state.consecutiveFailures >= 5) {
      status = "unhealthy"
      message = `Intelligence worker has ${state.consecutiveFailures} consecutive failures`
      recoveryReady = true
    } else if (state.consecutiveFailures >= 3) {
      status = "degraded"
      message = `Intelligence worker experiencing errors: ${state.consecutiveFailures} consecutive failures`
      recoveryReady = true
    } else if (state.pipelineFailures > 0) {
      status = "degraded"
      message = `${state.pipelineFailures} pipeline failure(s) detected`
      recoveryReady = true
    } else if (stalled) {
      status = "degraded"
      message = "Execution stalled, no activity detected for over 120 seconds"
      recoveryReady = true
    }

    return {
      workerId,
      status,
      sessionCount: sessions.length,
      consecutiveFailures: state.consecutiveFailures,
      pipelineFailures: state.pipelineFailures,
      stalledExecutions: stalled ? 1 : 0,
      recoveryReady,
      message,
      timestamp: new Date().toISOString(),
    }
  },

  async getConsecutiveFailures(workerId: string): Promise<number> {
    return healthStates.get(workerId)?.consecutiveFailures ?? 0
  },

  async getTotalErrors(workerId: string): Promise<number> {
    return healthStates.get(workerId)?.totalErrors ?? 0
  },

  async reset(workerId: string): Promise<void> {
    healthStates.delete(workerId)
  },
}
