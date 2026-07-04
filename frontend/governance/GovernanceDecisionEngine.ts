import type { GovernanceDecision } from "./types"
import { generateId } from "./shared"

const decisions = new Map<string, GovernanceDecision>()

export const GovernanceDecisionEngine = {
  async decide(sessionId: string, action: string, result: "allow" | "deny" | "review", reason: string, decidedBy: string = "GovernanceEngine"): Promise<GovernanceDecision> {
    const id = generateId("gov-dec")
    const decision: GovernanceDecision = {
      id,
      sessionId,
      action,
      result,
      reason,
      decidedBy,
      timestamp: new Date().toISOString(),
      overrides: null,
    }
    decisions.set(id, decision)
    return decision
  },

  async overrideDecision(decisionId: string, newResult: "allow" | "deny" | "review", reason: string, decidedBy: string): Promise<GovernanceDecision> {
    const existing = decisions.get(decisionId)
    if (!existing) throw new Error(`Decision not found: ${decisionId}`)

    const id = generateId("gov-dec")
    const decision: GovernanceDecision = {
      id,
      sessionId: existing.sessionId,
      action: existing.action,
      result: newResult,
      reason,
      decidedBy,
      timestamp: new Date().toISOString(),
      overrides: decisionId,
    }
    decisions.set(id, decision)
    return decision
  },

  async recordDecision(sessionId: string, action: string, result: "allow" | "deny" | "review" | "override", reason: string, decidedBy: string): Promise<GovernanceDecision> {
    if (result === "override") {
      const id = generateId("gov-dec")
      const decision: GovernanceDecision = {
        id,
        sessionId,
        action,
        result,
        reason,
        decidedBy,
        timestamp: new Date().toISOString(),
        overrides: null,
      }
      decisions.set(id, decision)
      return decision
    }
    return GovernanceDecisionEngine.decide(sessionId, action, result, reason, decidedBy)
  },

  async getDecision(decisionId: string): Promise<GovernanceDecision | null> {
    return decisions.get(decisionId) ?? null
  },

  async listDecisions(sessionId?: string): Promise<GovernanceDecision[]> {
    let result = Array.from(decisions.values())
    if (sessionId) result = result.filter((d) => d.sessionId === sessionId)
    return result.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
  },

  async decisionCount(): Promise<number> {
    return decisions.size
  },
}
