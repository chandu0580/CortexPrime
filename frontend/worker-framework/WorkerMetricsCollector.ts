import type { WorkerMetrics, WorkerState } from "./types"
import { WorkerHeartbeatManager } from "./WorkerHeartbeatManager"

const metricsStore = new Map<string, WorkerMetrics>()

export const WorkerMetricsCollector = {
  async collect(
    workerId: string,
    state: WorkerState,
    tasksCompleted: number = 0,
    tasksFailed: number = 0,
    startedAt: string,
  ): Promise<WorkerMetrics> {
    const uptimeMs = Date.now() - new Date(startedAt).getTime()
    const totalHeartbeats = await WorkerHeartbeatManager.getHeartbeatCount(workerId)
    const tasksRunning = state === "RUNNING" ? 1 : 0

    const metrics: WorkerMetrics = {
      workerId,
      uptimeMs,
      tasksCompleted,
      tasksFailed,
      tasksRunning,
      totalHeartbeats,
      averageTaskDurationMs: tasksCompleted > 0 ? uptimeMs / tasksCompleted : 0,
      errorRate: (tasksCompleted + tasksFailed) > 0 ? tasksFailed / (tasksCompleted + tasksFailed) : 0,
      lastMetricAt: new Date().toISOString(),
    }

    metricsStore.set(workerId, metrics)
    return metrics
  },

  async getMetrics(workerId: string): Promise<WorkerMetrics | null> {
    return metricsStore.get(workerId) ?? null
  },
}
