import type { ExecutionPolicy as ExecutionPolicyType, ExecutionPolicyRule } from "./types"

export type ExecutionPolicy = ExecutionPolicyType

const policies = new Map<string, ExecutionPolicy>()

export const ExecutionPolicyEngine = {
  async registerPolicy(policy: ExecutionPolicy): Promise<void> {
    policies.set(policy.id, policy)
  },

  async unregisterPolicy(policyId: string): Promise<void> {
    policies.delete(policyId)
  },

  async getPolicy(policyId: string): Promise<ExecutionPolicy | null> {
    return policies.get(policyId) ?? null
  },

  async getAllPolicies(): Promise<ExecutionPolicy[]> {
    return Array.from(policies.values())
  },

  async evaluateExecution(sessionId: string, action: string, data: Record<string, unknown>): Promise<{ allowed: boolean; reasons: string[] }> {
    const reasons: string[] = []
    const relevantPolicies = Array.from(policies.values())
      .filter((p) => p.enabled)
      .sort((a, b) => b.priority - a.priority)

    for (const policy of relevantPolicies) {
      for (const rule of policy.rules) {
        const result = this.evaluateRule(rule, { ...data, sessionId, action })
        if (policy.effect === "deny" && !result) {
          reasons.push(rule.message)
        }
      }
    }
    return { allowed: reasons.length === 0, reasons }
  },

  async evaluateConcurrency(sessionId: string, currentCount: number, maxConcurrency: number): Promise<{ allowed: boolean; reasons: string[] }> {
    const reasons: string[] = []
    const relevantPolicies = Array.from(policies.values())
      .filter((p) => p.category === "concurrency" && p.enabled)
      .sort((a, b) => b.priority - a.priority)

    for (const policy of relevantPolicies) {
      for (const rule of policy.rules) {
        const result = this.evaluateRule(rule, { currentCount, maxConcurrency })
        if (policy.effect === "deny" && !result) {
          reasons.push(rule.message)
        }
      }
    }

    if (currentCount >= maxConcurrency) {
      reasons.push(`Concurrency limit reached: ${currentCount} >= ${maxConcurrency}`)
    }

    return { allowed: reasons.length === 0, reasons }
  },

  async evaluateAssignment(sessionId: string, workerCount: number, taskCount: number): Promise<{ allowed: boolean; reasons: string[] }> {
    const reasons: string[] = []
    const relevantPolicies = Array.from(policies.values())
      .filter((p) => p.category === "assignment" && p.enabled)
      .sort((a, b) => b.priority - a.priority)

    for (const policy of relevantPolicies) {
      for (const rule of policy.rules) {
        const result = this.evaluateRule(rule, { workerCount, taskCount })
        if (policy.effect === "deny" && !result) {
          reasons.push(rule.message)
        }
      }
    }

    if (workerCount === 0) {
      reasons.push("No workers available for assignment")
    }

    return { allowed: reasons.length === 0, reasons }
  },

  evaluateRule(rule: ExecutionPolicyRule, data: Record<string, unknown>): boolean {
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
