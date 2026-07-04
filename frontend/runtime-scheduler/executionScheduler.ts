import type {
  ExecutionSchedule,
  ScheduleDecision,
  ExecutionTrigger,
  ExecutionDeadline,
  RetrySchedule,
  DeferredExecution,
  SchedulerMetrics,
  ScheduleRule,
  TriggerType,
} from "./types"
import { ScheduleRegistry } from "./ScheduleRegistry"
import { SchedulePolicyEngine } from "./SchedulePolicyEngine"
import { TriggerManager } from "./TriggerManager"
import { WindowManager } from "./WindowManager"
import { DeadlineManager } from "./DeadlineManager"
import { RetryScheduler } from "./RetryScheduler"
import { DeferredExecutionManager } from "./DeferredExecutionManager"
import { SchedulerMetricsCollector } from "./SchedulerMetricsCollector"
import { generateId } from "./shared"

export const executionScheduler = {
  async createSchedule(
    sessionId: string,
    taskId: string,
    name: string,
    triggerType: TriggerType,
    priority: number = 5,
    rules: ScheduleRule[] = [],
    scheduledAt?: string,
  ): Promise<ExecutionSchedule> {
    const trigger = await TriggerManager.createTrigger(triggerType, scheduledAt ?? null)

    const schedule: ExecutionSchedule = {
      id: generateId("schedule"),
      sessionId,
      taskId,
      name,
      trigger,
      window: null,
      deadline: null,
      retrySchedule: null,
      deferredExecution: null,
      rules: rules.length > 0 ? rules : [
        { id: generateId("rule"), name: "Minimum Priority", description: "Priority must be at least 1", condition: "priority >= 1", evaluation: "pass" },
      ],
      status: "active",
      priority,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      nextRunAt: triggerType === "immediate" ? new Date().toISOString() : (scheduledAt ?? null),
      lastRunAt: null,
    }

    await ScheduleRegistry.register(schedule)
    return schedule
  },

  async evaluateSchedule(scheduleId: string): Promise<ScheduleDecision> {
    const schedule = await ScheduleRegistry.getSchedule(scheduleId)
    if (!schedule) throw new Error(`Schedule not found: ${scheduleId}`)

    return SchedulePolicyEngine.evaluate(schedule)
  },

  async scheduleTask(
    scheduleId: string,
    triggerType: TriggerType,
    scheduledAt?: string,
  ): Promise<ExecutionSchedule> {
    const schedule = await ScheduleRegistry.getSchedule(scheduleId)
    if (!schedule) throw new Error(`Schedule not found: ${scheduleId}`)

    const trigger = await TriggerManager.createTrigger(triggerType, scheduledAt ?? null)
    const nextRunAt = triggerType === "immediate"
      ? new Date().toISOString()
      : (scheduledAt ?? schedule.nextRunAt)

    return ScheduleRegistry.updateSchedule(scheduleId, { trigger, nextRunAt })
  },

  async deferTask(scheduleId: string, until: string, reason: string): Promise<{
    schedule: ExecutionSchedule
    deferred: DeferredExecution
  }> {
    const schedule = await ScheduleRegistry.getSchedule(scheduleId)
    if (!schedule) throw new Error(`Schedule not found: ${scheduleId}`)

    const deferred = await DeferredExecutionManager.defer(scheduleId, until, reason)
    const updated = await ScheduleRegistry.updateSchedule(scheduleId, {
      deferredExecution: deferred,
      nextRunAt: until,
    })

    return { schedule: updated, deferred }
  },

  async resumeDeferred(deferredId: string): Promise<ExecutionSchedule> {
    const deferred = await DeferredExecutionManager.getDeferred(deferredId)
    if (!deferred) throw new Error(`Deferred execution not found: ${deferredId}`)

    await DeferredExecutionManager.resume(deferredId)
    const schedule = await ScheduleRegistry.getSchedule(deferred.originalScheduleId)
    if (!schedule) throw new Error(`Original schedule not found: ${deferred.originalScheduleId}`)

    return ScheduleRegistry.updateSchedule(deferred.originalScheduleId, {
      deferredExecution: null,
      nextRunAt: new Date().toISOString(),
    })
  },

  async triggerExecution(scheduleId: string): Promise<ScheduleDecision> {
    const schedule = await ScheduleRegistry.getSchedule(scheduleId)
    if (!schedule) throw new Error(`Schedule not found: ${scheduleId}`)

    const decision = await SchedulePolicyEngine.evaluate(schedule)

    if (decision.shouldExecute) {
      await ScheduleRegistry.updateSchedule(scheduleId, {
        lastRunAt: new Date().toISOString(),
        nextRunAt: null,
      })
    }

    return decision
  },

  async evaluateDeadline(scheduleId: string): Promise<ExecutionDeadline | null> {
    const schedule = await ScheduleRegistry.getSchedule(scheduleId)
    if (!schedule || !schedule.deadline) return null

    return DeadlineManager.evaluateDeadline(schedule.deadline, schedule.createdAt)
  },

  async calculateNextRun(scheduleId: string): Promise<string | null> {
    const schedule = await ScheduleRegistry.getSchedule(scheduleId)
    if (!schedule) throw new Error(`Schedule not found: ${scheduleId}`)

    const nextTrigger = await TriggerManager.calculateNextTriggerTime(schedule.trigger)
    if (nextTrigger) return nextTrigger

    if (schedule.window) {
      return WindowManager.getNextWindowOpen(schedule.window)
    }

    if (schedule.retrySchedule) {
      const nextRetry = await RetryScheduler.calculateNextRetry(schedule.retrySchedule)
      await ScheduleRegistry.updateSchedule(scheduleId, { retrySchedule: nextRetry })
      return nextRetry.nextRetryAt
    }

    return null
  },

  async cancelSchedule(scheduleId: string): Promise<ExecutionSchedule> {
    const schedule = await ScheduleRegistry.getSchedule(scheduleId)
    if (!schedule) throw new Error(`Schedule not found: ${scheduleId}`)

    if (schedule.deferredExecution) {
      await DeferredExecutionManager.cancelDeferred(schedule.deferredExecution.id)
    }

    return ScheduleRegistry.cancelSchedule(scheduleId)
  },

  async collectMetrics(): Promise<SchedulerMetrics> {
    const schedules = await ScheduleRegistry.getAllSchedules()
    return SchedulerMetricsCollector.collectMetrics(schedules)
  },
}
