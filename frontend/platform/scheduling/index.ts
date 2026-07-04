export type ScheduleTrigger = "immediate" | "cron" | "delay" | "dependency" | "manual"

export type ScheduleStatus = "active" | "paused" | "completed" | "cancelled"

export interface ScheduleDefinition {
  id: string
  sessionId: string
  taskId: string
  trigger: ScheduleTrigger
  cronExpression: string | null
  delayMs: number | null
  dependencyId: string | null
  maxRetries: number
}

export interface ScheduleCalendar {
  availableWindows: ScheduleWindow[]
  blockedWindows: ScheduleWindow[]
}

export interface ScheduleWindow {
  openAt: string
  closeAt: string
  timezone: string
  recurrence: "none" | "daily" | "weekly" | "monthly"
  daysOfWeek: number[]
}
