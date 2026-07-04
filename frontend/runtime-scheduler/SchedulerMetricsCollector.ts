import type { SchedulerMetrics, ExecutionSchedule } from "./types"
import { DeferredExecutionManager } from "./DeferredExecutionManager"

export const SchedulerMetricsCollector = {
  async collectMetrics(schedules: ExecutionSchedule[]): Promise<SchedulerMetrics> {
    const totalSchedules = schedules.length
    const activeSchedules = schedules.filter((s) => s.status === "active").length
    const pausedSchedules = schedules.filter((s) => s.status === "paused").length
    const completedSchedules = schedules.filter((s) => s.status === "completed").length
    const cancelledSchedules = schedules.filter((s) => s.status === "cancelled").length

    const tasksScheduled = schedules.filter((s) => s.nextRunAt !== null).length
    const tasksOverdue = schedules.filter((s) => s.deadline?.overdue).length
    const deferredCount = await DeferredExecutionManager.getDeferredCount()

    const now = new Date()
    const completed = schedules.filter(
      (s) => s.lastRunAt !== null && s.createdAt,
    )
    const totalDelayMs = completed.reduce((sum, s) => {
      if (s.lastRunAt && s.createdAt) {
        return sum + (new Date(s.lastRunAt).getTime() - new Date(s.createdAt).getTime())
      }
      return sum
    }, 0)

    return {
      totalSchedules,
      activeSchedules,
      pausedSchedules,
      completedSchedules: completedSchedules + cancelledSchedules,
      tasksScheduled,
      tasksDeferred: deferredCount,
      tasksExecuted: schedules.filter((s) => s.lastRunAt !== null).length,
      tasksOverdue,
      tasksRetried: schedules.filter((s) => s.retrySchedule && s.retrySchedule.retryCount > 0).length,
      averageDelayMs: completed.length > 0 ? totalDelayMs / completed.length : 0,
      decisionsApproved: 0,
      decisionsDeferred: deferredCount,
      decisionsDenied: 0,
    }
  },
}
