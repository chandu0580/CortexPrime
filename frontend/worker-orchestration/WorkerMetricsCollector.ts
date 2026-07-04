import type { WorkerMetrics } from "./types"
import { WorkerSessionManager } from "./WorkerSessionManager"
import { WorkerCoordinator } from "./WorkerCoordinator"
import { WorkerSynchronizationEngine } from "./WorkerSynchronizationEngine"
import { WorkerRecoveryEngine } from "./WorkerRecoveryEngine"

let lastMetrics: WorkerMetrics = {
  activeSessions: 0,
  completedSessions: 0,
  failedSessions: 0,
  activeWorkers: 0,
  completedWorkers: 0,
  failedWorkers: 0,
  synchronizationCount: 0,
  assignmentUtilization: {},
  recoveries: 0,
  avgExecutionDurationMs: 0,
  updatedAt: new Date().toISOString(),
}

export const WorkerMetricsCollector = {
  async collectMetrics(): Promise<WorkerMetrics> {
    const sessions = await WorkerSessionManager.getAll()
    const activeSessions = sessions.filter((s) => s.status === "executing" || s.status === "ready").length
    const completedSessions = sessions.filter((s) => s.status === "completed").length
    const failedSessions = sessions.filter((s) => s.status === "failed").length

    const workers = await WorkerCoordinator.getAllWorkers()
    const activeWorkers = workers.filter((w) => w.status === "running").length
    const failedWorkers = workers.filter((w) => w.status === "failed").length

    const allExecs = (await Promise.all(
      sessions.map((s) => WorkerCoordinator.getExecutionsBySession(s.id)),
    )).flat()
    const completedExecs = allExecs.filter((e) => e.status === "completed")
    const totalDurationMs = completedExecs.reduce((acc, e) => {
      return acc + (e.completedAt && e.startedAt ? new Date(e.completedAt).getTime() - new Date(e.startedAt).getTime() : 0)
    }, 0)

    const syncCount = await WorkerSynchronizationEngine.countCompleted()
    const recoveryCount = (await Promise.all(
      sessions.map((s) => WorkerRecoveryEngine.getRecoveriesBySession(s.id)),
    )).flat().length

    lastMetrics = {
      activeSessions,
      completedSessions,
      failedSessions,
      activeWorkers,
      completedWorkers: completedExecs.length,
      failedWorkers,
      synchronizationCount: syncCount,
      assignmentUtilization: {},
      recoveries: recoveryCount,
      avgExecutionDurationMs: completedExecs.length > 0 ? Math.round(totalDurationMs / completedExecs.length) : 0,
      updatedAt: new Date().toISOString(),
    }
    return lastMetrics
  },

  async getMetrics(): Promise<WorkerMetrics> {
    return lastMetrics
  },

  async recordExecutionTime(workerId: string, startMs: number, endMs: number): Promise<void> {
    const totalMs = lastMetrics.avgExecutionDurationMs * lastMetrics.completedWorkers
    const newTotal = totalMs + (endMs - startMs)
    lastMetrics.completedWorkers++
    lastMetrics.avgExecutionDurationMs = Math.round(newTotal / lastMetrics.completedWorkers)
    lastMetrics.updatedAt = new Date().toISOString()
  },
}
