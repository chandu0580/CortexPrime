import type { WorkerHealth } from "./types"
import { WorkerSessionManager } from "./WorkerSessionManager"
import { WorkerCoordinator } from "./WorkerCoordinator"

export const WorkerHealthManager = {
  async checkHealth(): Promise<WorkerHealth> {
    const sessions = await WorkerSessionManager.getAll()
    const activeSessions = sessions.filter((s) => s.status === "executing" || s.status === "ready").length

    const workers = await WorkerCoordinator.getAllWorkers()
    const stalledWorkers = workers.filter(
      (w) => w.status === "starting" || w.status === "pausing" || w.status === "stopping",
    ).length

    const workerFailures = workers.filter((w) => w.status === "failed").length

    const sessionFailures = sessions.filter((s) => s.status === "failed").length
    const syncFailures = 0

    const recoveryReady = workerFailures > 0 || sessionFailures > 0

    const issues: string[] = []
    if (workerFailures > 3) issues.push(`High worker failure count: ${workerFailures}`)
    if (stalledWorkers > 3) issues.push(`Stalled workers detected: ${stalledWorkers}`)
    if (sessionFailures > 5) issues.push(`High session failure count: ${sessionFailures}`)
    if (syncFailures > 3) issues.push(`Synchronization failures: ${syncFailures}`)

    const isHealthy = workerFailures === 0 && stalledWorkers === 0 && syncFailures === 0
    const isDegraded = workerFailures <= 3 && stalledWorkers <= 3 && syncFailures <= 3

    return {
      status: isHealthy ? "healthy" : isDegraded ? "degraded" : "unhealthy",
      activeSessions,
      workerFailures,
      stalledWorkers,
      unhealthyWorkers: workerFailures,
      synchronizationFailures: syncFailures,
      recoveryReady,
      lastCheckAt: new Date().toISOString(),
      issues,
    }
  },

  async isHealthy(): Promise<boolean> {
    const health = await this.checkHealth()
    return health.status === "healthy"
  },
}
