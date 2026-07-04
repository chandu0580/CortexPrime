import type { ExecutionDeadline } from "./types"
import { generateId } from "./shared"

const deadlines = new Map<string, ExecutionDeadline>()

export const DeadlineManager = {
  async createDeadline(
    absoluteDeadline: string | null = null,
    relativeDelayMs: number | null = null,
    gracePeriodMs: number = 0,
  ): Promise<ExecutionDeadline> {
    const deadline: ExecutionDeadline = {
      id: generateId("deadline"),
      absoluteDeadline,
      relativeDelayMs,
      overdue: false,
      overdueAt: null,
      gracePeriodMs,
    }
    deadlines.set(deadline.id, deadline)
    return deadline
  },

  async getDeadline(id: string): Promise<ExecutionDeadline | null> {
    return deadlines.get(id) ?? null
  },

  async evaluateDeadline(deadline: ExecutionDeadline, startedAt: string): Promise<ExecutionDeadline> {
    let overdue = false
    let overdueAt: string | null = null

    if (deadline.absoluteDeadline) {
      const absDeadline = new Date(deadline.absoluteDeadline)
      if (new Date() > absDeadline) {
        const withGrace = new Date(absDeadline.getTime() + deadline.gracePeriodMs)
        overdue = new Date() > withGrace
        overdueAt = overdue ? new Date().toISOString() : null
      }
    }

    if (deadline.relativeDelayMs && !overdue) {
      const started = new Date(startedAt)
      const deadlineTime = new Date(started.getTime() + deadline.relativeDelayMs + deadline.gracePeriodMs)
      overdue = new Date() > deadlineTime
      overdueAt = overdue ? new Date().toISOString() : null
    }

    const updated: ExecutionDeadline = { ...deadline, overdue, overdueAt }
    deadlines.set(deadline.id, updated)
    return updated
  },

  async isOverdue(deadline: ExecutionDeadline): Promise<boolean> {
    if (deadline.overdue) return true
    const reevaluated = await DeadlineManager.evaluateDeadline(deadline, new Date().toISOString())
    return reevaluated.overdue
  },

  async timeUntilDeadline(deadline: ExecutionDeadline): Promise<number | null> {
    if (deadline.absoluteDeadline) {
      const remaining = new Date(deadline.absoluteDeadline).getTime() - Date.now()
      return Math.max(0, remaining)
    }
    return null
  },

  async extendDeadline(deadlineId: string, additionalMs: number): Promise<ExecutionDeadline> {
    const deadline = deadlines.get(deadlineId)
    if (!deadline) throw new Error(`Deadline not found: ${deadlineId}`)
    const updated: ExecutionDeadline = {
      ...deadline,
      gracePeriodMs: deadline.gracePeriodMs + additionalMs,
      overdue: false,
      overdueAt: null,
    }
    deadlines.set(deadlineId, updated)
    return updated
  },
}
