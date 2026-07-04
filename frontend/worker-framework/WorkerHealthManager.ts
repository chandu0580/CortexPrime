import type { WorkerHealth, WorkerHealthStatus, WorkerState } from "./types"

const healthRecords = new Map<string, WorkerHealth>()

export const WorkerHealthManager = {
  async check(
    workerId: string,
    state: WorkerState,
    lastHeartbeatAt: string | null,
  ): Promise<WorkerHealth> {
    const existing = healthRecords.get(workerId)
    const consecutiveFailures = existing?.consecutiveFailures ?? 0
    const errorCount = existing?.errorCount ?? 0

    let status: WorkerHealthStatus
    let message: string

    if (state === "SHUTDOWN") {
      status = "unknown"
      message = "Worker is shut down"
    } else if (state === "RUNNING" || state === "READY") {
      if (lastHeartbeatAt && Date.now() - new Date(lastHeartbeatAt).getTime() < 30000) {
        status = "healthy"
        message = "Worker is healthy"
      } else if (lastHeartbeatAt) {
        status = "degraded"
        message = "Worker heartbeat is stale"
      } else {
        status = "degraded"
        message = "No heartbeat received"
      }
    } else if (state === "PAUSED") {
      status = "degraded"
      message = "Worker is paused"
    } else {
      status = "unhealthy"
      message = `Worker is in ${state} state`
    }

    const health: WorkerHealth = {
      workerId,
      status,
      lastHeartbeatAt,
      lastHealthCheckAt: new Date().toISOString(),
      consecutiveFailures: status === "healthy" ? 0 : consecutiveFailures + 1,
      errorCount: status === "unhealthy" ? errorCount + 1 : errorCount,
      message,
    }

    healthRecords.set(workerId, health)
    return health
  },

  async getHealth(workerId: string): Promise<WorkerHealth | null> {
    return healthRecords.get(workerId) ?? null
  },

  async isHealthy(workerId: string): Promise<boolean> {
    const health = healthRecords.get(workerId)
    return health?.status === "healthy"
  },
}
