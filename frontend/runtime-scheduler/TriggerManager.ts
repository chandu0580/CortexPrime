import type { ExecutionTrigger, TriggerType } from "./types"
import { generateId } from "./shared"

const triggers = new Map<string, ExecutionTrigger>()

export const TriggerManager = {
  async createTrigger(
    type: TriggerType,
    scheduledAt: string | null = null,
    dependencyId: string | null = null,
    externalSource: string | null = null,
    manualApprovalRequired: boolean = false,
  ): Promise<ExecutionTrigger> {
    const trigger: ExecutionTrigger = {
      id: generateId("trigger"),
      type,
      scheduledAt,
      dependencyId,
      externalSource,
      manualApprovalRequired,
    }
    triggers.set(trigger.id, trigger)
    return trigger
  },

  async getTrigger(id: string): Promise<ExecutionTrigger | null> {
    return triggers.get(id) ?? null
  },

  async isTriggerReady(trigger: ExecutionTrigger): Promise<boolean> {
    switch (trigger.type) {
      case "immediate":
        return true
      case "scheduled":
        return trigger.scheduledAt !== null && new Date(trigger.scheduledAt) <= new Date()
      case "dependency":
        return trigger.dependencyId !== null
      case "manual":
        return !trigger.manualApprovalRequired
      case "external":
        return trigger.externalSource !== null
      default:
        return false
    }
  },

  async calculateNextTriggerTime(trigger: ExecutionTrigger): Promise<string | null> {
    switch (trigger.type) {
      case "immediate":
        return new Date().toISOString()
      case "scheduled":
        return trigger.scheduledAt
      case "dependency":
      case "manual":
      case "external":
        return null
      default:
        return null
    }
  },

  async evaluateTriggers(): Promise<ExecutionTrigger[]> {
    const ready: ExecutionTrigger[] = []
    for (const trigger of triggers.values()) {
      if (await TriggerManager.isTriggerReady(trigger)) {
        ready.push(trigger)
      }
    }
    return ready
  },
}
