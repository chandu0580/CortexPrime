import type { MemoryPolicy, MemoryPolicyRule } from "./types"

const policies = new Map<string, MemoryPolicy>()

export const MemoryPolicyEngine = {
  async registerPolicy(policy: MemoryPolicy): Promise<void> {
    if (policies.has(policy.id)) throw new Error(`Memory policy ${policy.id} already exists`)
    policies.set(policy.id, { ...policy })
  },

  async updatePolicy(policy: MemoryPolicy): Promise<void> {
    if (!policies.has(policy.id)) throw new Error(`Memory policy ${policy.id} not found`)
    policies.set(policy.id, { ...policy })
  },

  async removePolicy(policyId: string): Promise<void> {
    if (!policies.has(policyId)) throw new Error(`Memory policy ${policyId} not found`)
    policies.delete(policyId)
  },

  async getPolicy(policyId: string): Promise<MemoryPolicy | null> {
    return policies.get(policyId) ?? null
  },

  async listPolicies(): Promise<MemoryPolicy[]> {
    return Array.from(policies.values()).sort((a, b) => b.priority - a.priority)
  },

  evaluateRule(rule: MemoryPolicyRule, context: Record<string, unknown>): { passed: boolean; message: string } {
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

  async checkRetention(entryAgeMs: number, maxRetentionMs: number): Promise<{ retained: boolean; reason: string }> {
    const retained = entryAgeMs <= maxRetentionMs
    return {
      retained,
      reason: retained
        ? `Entry age ${entryAgeMs}ms within retention limit ${maxRetentionMs}ms`
        : `Entry age ${entryAgeMs}ms exceeds retention limit ${maxRetentionMs}ms`,
    }
  },

  async checkExpiration(entryAgeMs: number, ttlMs: number): Promise<{ expired: boolean; reason: string }> {
    const expired = entryAgeMs >= ttlMs
    return {
      expired,
      reason: expired
        ? `Entry age ${entryAgeMs}ms exceeded TTL ${ttlMs}ms`
        : `Entry age ${entryAgeMs}ms within TTL ${ttlMs}ms`,
    }
  },

  async checkVisibility(
    entryScope: string,
    userScope: string,
  ): Promise<{ visible: boolean; reason: string }> {
    const scopeHierarchy: Record<string, number> = { session: 0, user: 1, organization: 2, global: 3 }
    const entryLevel = scopeHierarchy[entryScope] ?? 0
    const userLevel = scopeHierarchy[userScope] ?? 0
    const visible = userLevel >= entryLevel
    return {
      visible,
      reason: visible ? "Entry is visible to user scope" : "Entry scope exceeds user access level",
    }
  },

  async clearPolicies(): Promise<void> {
    policies.clear()
  },
}
