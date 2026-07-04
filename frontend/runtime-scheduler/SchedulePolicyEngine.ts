import type { ExecutionSchedule, ScheduleRule, ScheduleDecision, DecisionStatus, ScheduleWindow } from "./types"
import { generateId } from "./shared"

export const SchedulePolicyEngine = {
  async evaluate(schedule: ExecutionSchedule): Promise<ScheduleDecision> {
    const blockingFactors: string[] = []
    let shouldExecute = true

    for (const rule of schedule.rules) {
      const passed = evaluateCondition(rule.condition, schedule)
      if (!passed) {
        blockingFactors.push(rule.description)
      }
    }

    if (schedule.status !== "active") {
      shouldExecute = false
      blockingFactors.push(`Schedule status is ${schedule.status}, not active`)
    }

    if (schedule.trigger.manualApprovalRequired) {
      shouldExecute = false
      blockingFactors.push("Manual approval required")
    }

    if (schedule.deadline && schedule.deadline.overdue) {
      const withinGrace = schedule.deadline.gracePeriodMs > 0
      if (!withinGrace) {
        shouldExecute = false
        blockingFactors.push("Deadline passed with no grace period")
      }
    }

    let status: DecisionStatus
    if (shouldExecute) {
      status = "approved"
    } else if (blockingFactors.some((f) => f.includes("Manual approval"))) {
      status = "waiting"
    } else {
      status = "denied"
    }

    const executeAt = shouldExecute ? (schedule.nextRunAt ?? new Date().toISOString()) : null

    return {
      id: generateId("decision"),
      scheduleId: schedule.id,
      status,
      shouldExecute,
      executeAt,
      reason: shouldExecute
        ? "All scheduling conditions met"
        : `Blocked by: ${blockingFactors.join("; ")}`,
      blockingFactors,
      evaluatedAt: new Date().toISOString(),
    }
  },

  async addRule(schedule: ExecutionSchedule, rule: ScheduleRule): Promise<ExecutionSchedule> {
    return {
      ...schedule,
      rules: [...schedule.rules, rule],
      updatedAt: new Date().toISOString(),
    }
  },
}

function evaluateCondition(condition: string, schedule: ExecutionSchedule): boolean {
  switch (condition) {
    case "priority >= 1":
      return schedule.priority >= 1
    case "priority >= 5":
      return schedule.priority >= 5
    case "priority >= 8":
      return schedule.priority >= 8
    case "has_window":
      return schedule.window !== null
    case "window_open":
      if (!schedule.window) return true
      return isWindowOpen(schedule.window)
    case "no_deadline_overdue":
      return !schedule.deadline?.overdue
    case "not_deferred":
      return schedule.deferredExecution === null
    case "retry_available":
      if (!schedule.retrySchedule) return true
      return schedule.retrySchedule.retryCount < schedule.retrySchedule.maxRetries
    default:
      return true
  }
}

function isWindowOpen(window: ScheduleWindow): boolean {
  const now = new Date()
  const open = new Date(window.openAt)
  const close = new Date(window.closeAt)
  return now >= open && now <= close
}
