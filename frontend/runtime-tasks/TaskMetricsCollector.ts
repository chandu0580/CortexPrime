import type { TaskMetrics, ExecutionTask } from "./types"
import { TaskCheckpointManager } from "./TaskCheckpointManager"

export const TaskMetricsCollector = {
  async collectMetrics(tasks: ExecutionTask[]): Promise<TaskMetrics> {
    const totalTasks = tasks.length
    const activeTasks = tasks.filter((t) => ["ASSIGNED", "RUNNING", "WAITING"].includes(t.state)).length
    const queuedTasks = tasks.filter((t) => ["QUEUED", "READY"].includes(t.state)).length
    const completedTasks = tasks.filter((t) => t.state === "COMPLETED").length
    const failedTasks = tasks.filter((t) => t.state === "FAILED").length
    const cancelledTasks = tasks.filter((t) => t.state === "CANCELLED").length
    const waitingTasks = tasks.filter((t) => t.state === "WAITING").length

    const completedWithDuration = tasks.filter(
      (t) => t.state === "COMPLETED" && t.startedAt && t.completedAt,
    )
    const totalDurationMs = completedWithDuration.reduce((sum, t) => {
      return sum + (new Date(t.completedAt!).getTime() - new Date(t.startedAt!).getTime())
    }, 0)
    const averageCompletionTimeMs = completedWithDuration.length > 0
      ? totalDurationMs / completedWithDuration.length
      : 0

    const totalCheckpoints = await TaskCheckpointManager.getTotalCheckpointCount()

    return {
      totalTasks,
      activeTasks,
      queuedTasks,
      completedTasks,
      failedTasks,
      cancelledTasks,
      waitingTasks,
      averageCompletionTimeMs,
      totalCheckpoints,
      totalBatches: 0,
      queueDepth: queuedTasks,
    }
  },
}
