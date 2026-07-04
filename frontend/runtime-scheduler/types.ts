export type TriggerType = "immediate" | "scheduled" | "dependency" | "manual" | "external"

export type ScheduleStatus = "active" | "paused" | "completed" | "cancelled"

export type WindowRecurrence = "none" | "daily" | "weekly" | "monthly"

export type DecisionStatus = "approved" | "deferred" | "denied" | "waiting"

export interface ExecutionSchedule {
  id: string
  sessionId: string
  taskId: string
  name: string
  trigger: ExecutionTrigger
  window: ScheduleWindow | null
  deadline: ExecutionDeadline | null
  retrySchedule: RetrySchedule | null
  deferredExecution: DeferredExecution | null
  rules: ScheduleRule[]
  status: ScheduleStatus
  priority: number
  createdAt: string
  updatedAt: string
  nextRunAt: string | null
  lastRunAt: string | null
}

export interface ScheduleRule {
  id: string
  name: string
  description: string
  condition: string
  evaluation: "pass" | "fail" | "skip"
}

export interface ScheduleWindow {
  id: string
  openAt: string
  closeAt: string
  timezone: string
  recurrence: WindowRecurrence
  daysOfWeek: number[]
}

export interface ExecutionTrigger {
  id: string
  type: TriggerType
  scheduledAt: string | null
  dependencyId: string | null
  externalSource: string | null
  manualApprovalRequired: boolean
}

export interface ExecutionDeadline {
  id: string
  absoluteDeadline: string | null
  relativeDelayMs: number | null
  overdue: boolean
  overdueAt: string | null
  gracePeriodMs: number
}

export interface RetrySchedule {
  id: string
  maxRetries: number
  retryCount: number
  baseDelayMs: number
  maxDelayMs: number
  backoffMultiplier: number
  nextRetryAt: string | null
  lastRetryAt: string | null
}

export interface DeferredExecution {
  id: string
  originalScheduleId: string
  deferredUntil: string
  reason: string
  autoResume: boolean
  resumedAt: string | null
}

export interface ExecutionCalendar {
  id: string
  sessionId: string
  availableWindows: ScheduleWindow[]
  blockedWindows: ScheduleWindow[]
  currentWindow: ScheduleWindow | null
}

export interface ScheduleDecision {
  id: string
  scheduleId: string
  status: DecisionStatus
  shouldExecute: boolean
  executeAt: string | null
  reason: string
  blockingFactors: string[]
  evaluatedAt: string
}

export interface SchedulerMetrics {
  totalSchedules: number
  activeSchedules: number
  pausedSchedules: number
  completedSchedules: number
  tasksScheduled: number
  tasksDeferred: number
  tasksExecuted: number
  tasksOverdue: number
  tasksRetried: number
  averageDelayMs: number
  decisionsApproved: number
  decisionsDeferred: number
  decisionsDenied: number
}
