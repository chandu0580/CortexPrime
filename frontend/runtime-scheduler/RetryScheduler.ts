import type { RetrySchedule } from "./types"
import { generateId } from "./shared"

const retrySchedules = new Map<string, RetrySchedule>()

export const RetryScheduler = {
  async createRetrySchedule(
    maxRetries: number = 3,
    baseDelayMs: number = 1000,
    maxDelayMs: number = 60000,
    backoffMultiplier: number = 2,
  ): Promise<RetrySchedule> {
    const schedule: RetrySchedule = {
      id: generateId("retry"),
      maxRetries,
      retryCount: 0,
      baseDelayMs,
      maxDelayMs,
      backoffMultiplier,
      nextRetryAt: null,
      lastRetryAt: null,
    }
    retrySchedules.set(schedule.id, schedule)
    return schedule
  },

  async getRetrySchedule(id: string): Promise<RetrySchedule | null> {
    return retrySchedules.get(id) ?? null
  },

  async calculateNextRetry(schedule: RetrySchedule): Promise<RetrySchedule> {
    if (schedule.retryCount >= schedule.maxRetries) {
      return { ...schedule, nextRetryAt: null }
    }

    const delay = Math.min(
      schedule.baseDelayMs * Math.pow(schedule.backoffMultiplier, schedule.retryCount),
      schedule.maxDelayMs,
    )

    const nextRetryAt = new Date(Date.now() + delay).toISOString()
    return { ...schedule, nextRetryAt }
  },

  async recordRetry(schedule: RetrySchedule): Promise<RetrySchedule> {
    const withNext = await RetryScheduler.calculateNextRetry(schedule)
    const updated: RetrySchedule = {
      ...withNext,
      retryCount: schedule.retryCount + 1,
      lastRetryAt: new Date().toISOString(),
    }
    retrySchedules.set(schedule.id, updated)
    return updated
  },

  async resetRetrySchedule(scheduleId: string): Promise<RetrySchedule> {
    const schedule = retrySchedules.get(scheduleId)
    if (!schedule) throw new Error(`Retry schedule not found: ${scheduleId}`)
    const updated: RetrySchedule = {
      ...schedule,
      retryCount: 0,
      nextRetryAt: null,
      lastRetryAt: null,
    }
    retrySchedules.set(scheduleId, updated)
    return updated
  },

  async isRetryAvailable(schedule: RetrySchedule): Promise<boolean> {
    return schedule.retryCount < schedule.maxRetries
  },

  async getRetryDelay(schedule: RetrySchedule): Promise<number> {
    return Math.min(
      schedule.baseDelayMs * Math.pow(schedule.backoffMultiplier, schedule.retryCount),
      schedule.maxDelayMs,
    )
  },
}
