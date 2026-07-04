import type { CoordinationDecision, CoordinationConflict, ConflictResolution } from "./types"
import { generateId } from "./shared"

const decisions = new Map<string, CoordinationDecision>()
const conflicts = new Map<string, CoordinationConflict>()
const resolutions = new Map<string, ConflictResolution>()

export const CoordinationDecisionEngine = {
  async evaluateExecution(sessionId: string, reason: string): Promise<CoordinationDecision> {
    const decision: CoordinationDecision = {
      id: generateId("cdec"),
      sessionId,
      type: "execute",
      reason,
      timestamp: new Date().toISOString(),
      decidedBy: "CoordinationDecisionEngine",
    }
    decisions.set(decision.id, decision)
    return decision
  },

  async resolveConflict(
    sessionId: string,
    type: "resource" | "dependency" | "priority" | "state",
    description: string,
    involvedWorkers: string[],
    involvedTasks: string[],
    resolution: string,
    resolvedBy: string,
  ): Promise<{ conflict: CoordinationConflict; resolution: ConflictResolution }> {
    const conflict: CoordinationConflict = {
      id: generateId("conf"),
      sessionId,
      type,
      description,
      involvedWorkers,
      involvedTasks,
      detectedAt: new Date().toISOString(),
      resolved: true,
    }
    conflicts.set(conflict.id, conflict)

    const resolutionRecord: ConflictResolution = {
      id: generateId("cres"),
      conflictId: conflict.id,
      resolution,
      action: "resolve",
      resolvedBy,
      resolvedAt: new Date().toISOString(),
    }
    resolutions.set(resolutionRecord.id, resolutionRecord)
    return { conflict, resolution: resolutionRecord }
  },

  async determineNextAction(sessionId: string, completed: number, total: number, failedCount: number): Promise<CoordinationDecision> {
    let type: CoordinationDecision["type"]
    let reason: string

    if (failedCount > 0 && failedCount <= Math.ceil(total * 0.2)) {
      type = "retry"
      reason = `${failedCount} of ${total} tasks failed, retrying`
    } else if (failedCount > Math.ceil(total * 0.5)) {
      type = "abort"
      reason = `${failedCount} of ${total} tasks failed, aborting session`
    } else if (completed === total) {
      type = "execute"
      reason = "All tasks completed, proceeding to next stage"
    } else {
      type = "execute"
      reason = `${completed} of ${total} tasks completed, continuing execution`
    }

    const decision: CoordinationDecision = {
      id: generateId("cdec"),
      sessionId,
      type,
      reason,
      timestamp: new Date().toISOString(),
      decidedBy: "CoordinationDecisionEngine",
    }
    decisions.set(decision.id, decision)
    return decision
  },

  async escalateDecision(sessionId: string, reason: string): Promise<CoordinationDecision> {
    const decision: CoordinationDecision = {
      id: generateId("cdec"),
      sessionId,
      type: "escalate",
      reason,
      timestamp: new Date().toISOString(),
      decidedBy: "CoordinationDecisionEngine",
    }
    decisions.set(decision.id, decision)
    return decision
  },

  async getDecision(id: string): Promise<CoordinationDecision | null> {
    return decisions.get(id) ?? null
  },

  async listDecisions(sessionId?: string): Promise<CoordinationDecision[]> {
    let result = Array.from(decisions.values())
    if (sessionId) result = result.filter((d) => d.sessionId === sessionId)
    return result.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
  },

  async getConflicts(sessionId?: string): Promise<CoordinationConflict[]> {
    let result = Array.from(conflicts.values())
    if (sessionId) result = result.filter((c) => c.sessionId === sessionId)
    return result
  },
}
