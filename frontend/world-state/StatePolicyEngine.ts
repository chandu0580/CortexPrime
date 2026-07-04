import type { StatePolicy, StatePolicyRule } from "./types"

const policies = new Map<string, StatePolicy>()

export const StatePolicyEngine = {
  async registerPolicy(policy: StatePolicy): Promise<void> {
    if (policies.has(policy.id)) throw new Error(`State policy ${policy.id} already exists`)
    policies.set(policy.id, { ...policy })
  },

  async updatePolicy(policy: StatePolicy): Promise<void> {
    if (!policies.has(policy.id)) throw new Error(`State policy ${policy.id} not found`)
    policies.set(policy.id, { ...policy })
  },

  async removePolicy(policyId: string): Promise<void> {
    if (!policies.has(policyId)) throw new Error(`State policy ${policyId} not found`)
    policies.delete(policyId)
  },

  async getPolicy(policyId: string): Promise<StatePolicy | null> {
    return policies.get(policyId) ?? null
  },

  async listPolicies(): Promise<StatePolicy[]> {
    return Array.from(policies.values()).sort((a, b) => b.priority - a.priority)
  },

  evaluateRule(rule: StatePolicyRule, context: Record<string, unknown>): { passed: boolean; message: string } {
    const contextValue = context[rule.field]

    switch (rule.operator) {
      case "eq":
        return contextValue === rule.value
          ? { passed: true, message: "" }
          : { passed: false, message: rule.message }
      case "neq":
        return contextValue !== rule.value
          ? { passed: true, message: "" }
          : { passed: false, message: rule.message }
      case "gt":
        return Number(contextValue) > Number(rule.value)
          ? { passed: true, message: "" }
          : { passed: false, message: rule.message }
      case "gte":
        return Number(contextValue) >= Number(rule.value)
          ? { passed: true, message: "" }
          : { passed: false, message: rule.message }
      case "lt":
        return Number(contextValue) < Number(rule.value)
          ? { passed: true, message: "" }
          : { passed: false, message: rule.message }
      case "lte":
        return Number(contextValue) <= Number(rule.value)
          ? { passed: true, message: "" }
          : { passed: false, message: rule.message }
      case "in":
        return Array.isArray(rule.value) && rule.value.includes(contextValue)
          ? { passed: true, message: "" }
          : { passed: false, message: rule.message }
      case "not_in":
        return Array.isArray(rule.value) && !rule.value.includes(contextValue)
          ? { passed: true, message: "" }
          : { passed: false, message: rule.message }
      case "exists":
        return contextValue !== undefined && contextValue !== null
          ? { passed: true, message: "" }
          : { passed: false, message: rule.message }
      case "not_exists":
        return contextValue === undefined || contextValue === null
          ? { passed: true, message: "" }
          : { passed: false, message: rule.message }
      case "matches": {
        if (typeof rule.value !== "string" || typeof contextValue !== "string") {
          return { passed: false, message: rule.message }
        }
        try {
          const regex = new RegExp(rule.value)
          return regex.test(contextValue)
            ? { passed: true, message: "" }
            : { passed: false, message: rule.message }
        } catch {
          return { passed: false, message: `Invalid regex pattern: ${rule.value}` }
        }
      }
      default:
        return { passed: true, message: "" }
    }
  },

  async evaluate(
    context: Record<string, unknown>,
  ): Promise<{ allowed: boolean; policyId: string | null; reasons: string[] }> {
    const sorted = Array.from(policies.values())
      .filter((p) => p.enabled)
      .sort((a, b) => b.priority - a.priority)

    for (const policy of sorted) {
      const results = policy.rules.map((rule) => this.evaluateRule(rule, context))
      const allPassed = results.every((r) => r.passed)

      if (allPassed) {
        switch (policy.effect) {
          case "allow":
            return { allowed: true, policyId: policy.id, reasons: [`Allowed by policy ${policy.name}`] }
          case "deny":
            return { allowed: false, policyId: policy.id, reasons: [`Denied by policy ${policy.name}`] }
          case "audit":
            return { allowed: true, policyId: policy.id, reasons: [`Audited by policy ${policy.name}`] }
        }
      }
    }

    return { allowed: true, policyId: null, reasons: ["No matching policy, default allow"] }
  },

  async checkOwnership(entryOwner: string, actor: string): Promise<{ authorized: boolean; reason: string }> {
    const authorized = entryOwner === actor || actor === "system" || actor === "admin"
    return {
      authorized,
      reason: authorized ? "Actor is authorized for this state entry" : `Actor ${actor} does not own entry owned by ${entryOwner}`,
    }
  },

  async checkVisibility(entryScope: string, actorScope: string): Promise<{ visible: boolean; reason: string }> {
    const hierarchy: Record<string, number> = { global: 3, domain: 2, session: 1, worker: 0, capability: 0 }
    const entryLevel = hierarchy[entryScope] ?? 0
    const actorLevel = hierarchy[actorScope] ?? 0
    const visible = actorLevel >= entryLevel
    return {
      visible,
      reason: visible ? "State entry is visible" : "State entry scope exceeds actor scope",
    }
  },

  async clearPolicies(): Promise<void> {
    policies.clear()
  },
}
