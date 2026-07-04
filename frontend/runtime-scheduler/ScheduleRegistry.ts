import type { ExecutionSchedule, ScheduleStatus } from "./types"
import { generateId } from "./shared"

const schedules = new Map<string, ExecutionSchedule>()

export const ScheduleRegistry = {
  async register(schedule: ExecutionSchedule): Promise<ExecutionSchedule> {
    schedules.set(schedule.id, schedule)
    return schedule
  },

  async getSchedule(scheduleId: string): Promise<ExecutionSchedule | null> {
    return schedules.get(scheduleId) ?? null
  },

  async updateSchedule(scheduleId: string, updates: Partial<ExecutionSchedule>): Promise<ExecutionSchedule> {
    const schedule = schedules.get(scheduleId)
    if (!schedule) throw new Error(`Schedule not found: ${scheduleId}`)
    const updated: ExecutionSchedule = {
      ...schedule,
      ...updates,
      updatedAt: new Date().toISOString(),
    }
    schedules.set(scheduleId, updated)
    return updated
  },

  async cancelSchedule(scheduleId: string): Promise<ExecutionSchedule> {
    return ScheduleRegistry.updateSchedule(scheduleId, { status: "cancelled" })
  },

  async pauseSchedule(scheduleId: string): Promise<ExecutionSchedule> {
    return ScheduleRegistry.updateSchedule(scheduleId, { status: "paused" })
  },

  async resumeSchedule(scheduleId: string): Promise<ExecutionSchedule> {
    return ScheduleRegistry.updateSchedule(scheduleId, { status: "active" })
  },

  async getSchedulesBySession(sessionId: string): Promise<ExecutionSchedule[]> {
    return Array.from(schedules.values()).filter((s) => s.sessionId === sessionId)
  },

  async getSchedulesByTask(taskId: string): Promise<ExecutionSchedule[]> {
    return Array.from(schedules.values()).filter((s) => s.taskId === taskId)
  },

  async getActiveSchedules(): Promise<ExecutionSchedule[]> {
    return Array.from(schedules.values()).filter((s) => s.status === "active")
  },

  async getDueSchedules(): Promise<ExecutionSchedule[]> {
    const now = new Date()
    return Array.from(schedules.values()).filter(
      (s) => s.status === "active" && s.nextRunAt && new Date(s.nextRunAt) <= now,
    )
  },

  async getScheduleCount(): Promise<number> {
    return schedules.size
  },

  async getAllSchedules(): Promise<ExecutionSchedule[]> {
    return Array.from(schedules.values())
  },
}
