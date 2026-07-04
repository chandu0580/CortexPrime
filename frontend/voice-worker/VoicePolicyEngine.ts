import type { VoicePolicy, VoicePolicyEffect } from "./types"

const policies = new Map<string, VoicePolicy>()

export const VoicePolicyEngine = {
  async registerPolicy(policy: VoicePolicy): Promise<void> {
    if (policies.has(policy.id)) {
      throw new Error(`Voice policy ${policy.id} already exists`)
    }
    policies.set(policy.id, { ...policy })
  },

  async updatePolicy(policy: VoicePolicy): Promise<void> {
    if (!policies.has(policy.id)) {
      throw new Error(`Voice policy ${policy.id} not found`)
    }
    policies.set(policy.id, { ...policy })
  },

  async removePolicy(policyId: string): Promise<void> {
    if (!policies.has(policyId)) {
      throw new Error(`Voice policy ${policyId} not found`)
    }
    policies.delete(policyId)
  },

  async getPolicy(policyId: string): Promise<VoicePolicy | null> {
    return policies.get(policyId) ?? null
  },

  async listPolicies(): Promise<VoicePolicy[]> {
    return Array.from(policies.values()).sort((a, b) => b.priority - a.priority)
  },

  async evaluateAction(
    action: string,
    context: Record<string, unknown>,
  ): Promise<{ allowed: boolean; effect: VoicePolicyEffect; policyId: string | null; reason: string }> {
    const sorted = Array.from(policies.values())
      .filter((p) => p.enabled)
      .sort((a, b) => b.priority - a.priority)

    for (const policy of sorted) {
      if (!policy.actions.includes(action) && !policy.actions.includes("*")) {
        continue
      }

      const conditionsMet = this.evaluateConditions(policy.conditions, context)

      if (conditionsMet) {
        switch (policy.effect) {
          case "allow":
            return { allowed: true, effect: "allow", policyId: policy.id, reason: `Allowed by policy ${policy.name}` }
          case "deny":
            return { allowed: false, effect: "deny", policyId: policy.id, reason: `Denied by policy ${policy.name}` }
          case "audit":
            return { allowed: true, effect: "audit", policyId: policy.id, reason: `Audited by policy ${policy.name}` }
        }
      }
    }

    return { allowed: true, effect: "allow", policyId: null, reason: "No matching policy, default allow" }
  },

  evaluateConditions(
    conditions: Record<string, unknown>,
    context: Record<string, unknown>,
  ): boolean {
    for (const [key, value] of Object.entries(conditions)) {
      const contextValue = context[key]
      if (contextValue === undefined) {
        return false
      }
      if (typeof value === "object" && value !== null && !Array.isArray(value)) {
        const cond = value as Record<string, unknown>
        if (cond["eq"] !== undefined && contextValue !== cond["eq"]) return false
        if (cond["neq"] !== undefined && contextValue === cond["neq"]) return false
        if (cond["gt"] !== undefined && Number(contextValue) <= Number(cond["gt"])) return false
        if (cond["gte"] !== undefined && Number(contextValue) < Number(cond["gte"])) return false
        if (cond["lt"] !== undefined && Number(contextValue) >= Number(cond["lt"])) return false
        if (cond["lte"] !== undefined && Number(contextValue) > Number(cond["lte"])) return false
        if (cond["in"] !== undefined && Array.isArray(cond["in"]) && !cond["in"].includes(contextValue)) return false
      } else {
        if (contextValue !== value) return false
      }
    }
    return true
  },

  async validateSessionAction(
    sessionId: string,
    action: string,
    context: Record<string, unknown>,
  ): Promise<{ allowed: boolean; reason: string }> {
    const result = await this.evaluateAction(action, { ...context, sessionId })
    return { allowed: result.allowed, reason: result.reason }
  },

  async clearPolicies(): Promise<void> {
    policies.clear()
  },
}
