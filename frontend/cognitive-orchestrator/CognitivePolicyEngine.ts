import type { CognitivePolicy as CognitivePolicyType, CognitivePolicyRule, CognitiveSession, CognitiveContext } from "./types"

export type CognitivePolicy = CognitivePolicyType

const policies = new Map<string, CognitivePolicy>()

export const CognitivePolicyEngine = {
  async registerPolicy(policy: CognitivePolicy): Promise<void> {
    policies.set(policy.id, policy)
  },

  async unregisterPolicy(policyId: string): Promise<void> {
    policies.delete(policyId)
  },

  async getPolicy(policyId: string): Promise<CognitivePolicy | null> {
    return policies.get(policyId) ?? null
  },

  async getAllPolicies(): Promise<CognitivePolicy[]> {
    return Array.from(policies.values())
  },

  async evaluateAvailability(requiredWorkers: string[]): Promise<{ allowed: boolean; reasons: string[] }> {
    const reasons: string[] = []
    const relevantPolicies = Array.from(policies.values())
      .filter((p) => p.category === "availability" && p.enabled)
      .sort((a, b) => b.priority - a.priority)

    if (relevantPolicies.length === 0) return { allowed: true, reasons: [] }

    for (const policy of relevantPolicies) {
      for (const rule of policy.rules) {
        const result = this.evaluateRule(rule, { requiredWorkers })
        if (policy.effect === "deny" && !result) {
          reasons.push(rule.message)
        }
      }
    }
    return { allowed: reasons.length === 0, reasons }
  },

  async evaluateContext(session: CognitiveSession, context: CognitiveContext): Promise<{ allowed: boolean; reasons: string[] }> {
    const reasons: string[] = []
    const relevantPolicies = Array.from(policies.values())
      .filter((p) => p.category === "context" && p.enabled)
      .sort((a, b) => b.priority - a.priority)

    for (const policy of relevantPolicies) {
      for (const rule of policy.rules) {
        const result = this.evaluateRule(rule, { sessionId: session.id, contextId: context.id, entries: context.memoryEntries.length })
        if (policy.effect === "deny" && !result) {
          reasons.push(rule.message)
        }
      }
    }
    return { allowed: reasons.length === 0, reasons }
  },

  async evaluateMemory(memoryEntryCount: number, requiredTypes: string[]): Promise<{ allowed: boolean; reasons: string[] }> {
    const reasons: string[] = []
    const relevantPolicies = Array.from(policies.values())
      .filter((p) => p.category === "memory" && p.enabled)
      .sort((a, b) => b.priority - a.priority)

    for (const policy of relevantPolicies) {
      for (const rule of policy.rules) {
        const result = this.evaluateRule(rule, { entryCount: memoryEntryCount, requiredTypes })
        if (policy.effect === "deny" && !result) {
          reasons.push(rule.message)
        }
      }
    }
    return { allowed: reasons.length === 0, reasons }
  },

  async evaluateGraph(entityCount: number, relationshipCount: number): Promise<{ allowed: boolean; reasons: string[] }> {
    const reasons: string[] = []
    const relevantPolicies = Array.from(policies.values())
      .filter((p) => p.category === "graph" && p.enabled)
      .sort((a, b) => b.priority - a.priority)

    for (const policy of relevantPolicies) {
      for (const rule of policy.rules) {
        const result = this.evaluateRule(rule, { entityCount, relationshipCount })
        if (policy.effect === "deny" && !result) {
          reasons.push(rule.message)
        }
      }
    }
    return { allowed: reasons.length === 0, reasons }
  },

  async evaluateState(stateKeyCount: number, conflictCount: number): Promise<{ allowed: boolean; reasons: string[] }> {
    const reasons: string[] = []
    const relevantPolicies = Array.from(policies.values())
      .filter((p) => p.category === "state" && p.enabled)
      .sort((a, b) => b.priority - a.priority)

    for (const policy of relevantPolicies) {
      for (const rule of policy.rules) {
        const result = this.evaluateRule(rule, { stateKeyCount, conflictCount })
        if (policy.effect === "deny" && !result) {
          reasons.push(rule.message)
        }
      }
    }
    return { allowed: reasons.length === 0, reasons }
  },

  evaluateRule(rule: CognitivePolicyRule, data: Record<string, unknown>): boolean {
    const value = data[rule.field]
    if (value === undefined) return rule.operator === "exists" ? false : true

    switch (rule.operator) {
      case "exists":
        return value !== undefined && value !== null
      case "equals":
        return value === rule.value
      case "gte":
        return typeof value === "number" && typeof rule.value === "number" && value >= rule.value
      case "lte":
        return typeof value === "number" && typeof rule.value === "number" && value <= rule.value
      case "in":
        return Array.isArray(rule.value) && rule.value.includes(value)
      case "not_in":
        return Array.isArray(rule.value) && !rule.value.includes(value)
      default:
        return true
    }
  },

  async countViolations(): Promise<number> {
    return Array.from(policies.values()).filter((p) => !p.enabled).length
  },
}
