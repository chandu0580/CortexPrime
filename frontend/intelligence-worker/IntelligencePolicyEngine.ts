import type { IntelligencePolicy, IntelligencePolicyRule, IntelligencePolicyEffect } from "./types"

const policies = new Map<string, IntelligencePolicy>()

export const IntelligencePolicyEngine = {
  async registerPolicy(policy: IntelligencePolicy): Promise<void> {
    if (policies.has(policy.id)) throw new Error(`Intelligence policy ${policy.id} already exists`)
    policies.set(policy.id, { ...policy })
  },

  async updatePolicy(policy: IntelligencePolicy): Promise<void> {
    if (!policies.has(policy.id)) throw new Error(`Intelligence policy ${policy.id} not found`)
    policies.set(policy.id, { ...policy })
  },

  async removePolicy(policyId: string): Promise<void> {
    if (!policies.has(policyId)) throw new Error(`Intelligence policy ${policyId} not found`)
    policies.delete(policyId)
  },

  async getPolicy(policyId: string): Promise<IntelligencePolicy | null> {
    return policies.get(policyId) ?? null
  },

  async listPolicies(): Promise<IntelligencePolicy[]> {
    return Array.from(policies.values()).sort((a, b) => b.priority - a.priority)
  },

  evaluateRule(rule: IntelligencePolicyRule, context: Record<string, unknown>): { passed: boolean; message: string } {
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
      default:
        return { passed: true, message: "" }
    }
  },

  async evaluate(
    context: Record<string, unknown>,
  ): Promise<{ allowed: boolean; effect: IntelligencePolicyEffect; policyId: string | null; reasons: string[] }> {
    const sorted = Array.from(policies.values())
      .filter((p) => p.enabled)
      .sort((a, b) => b.priority - a.priority)

    for (const policy of sorted) {
      const results = policy.rules.map((rule) => this.evaluateRule(rule, context))
      const allPassed = results.every((r) => r.passed)

      if (allPassed) {
        switch (policy.effect) {
          case "allow":
            return { allowed: true, effect: "allow", policyId: policy.id, reasons: [`Allowed by policy ${policy.name}`] }
          case "deny":
            return { allowed: false, effect: "deny", policyId: policy.id, reasons: [`Denied by policy ${policy.name}`] }
          case "audit":
            return { allowed: true, effect: "audit", policyId: policy.id, reasons: [`Audited by policy ${policy.name}`] }
        }
      }
    }

    return { allowed: true, effect: "allow", policyId: null, reasons: ["No matching policy, default allow"] }
  },

  async checkEvidenceCompleteness(
    evidenceCount: number,
    requiredCount: number,
  ): Promise<{ complete: boolean; reason: string }> {
    const complete = evidenceCount >= requiredCount
    return {
      complete,
      reason: complete ? `Evidence count ${evidenceCount} meets requirement of ${requiredCount}` : `Evidence count ${evidenceCount} is below required ${requiredCount}`,
    }
  },

  async checkConfidenceThreshold(
    score: number,
    threshold: number,
  ): Promise<{ passed: boolean; reason: string }> {
    const passed = score >= threshold
    return {
      passed,
      reason: passed ? `Confidence score ${score} meets threshold ${threshold}` : `Confidence score ${score} is below threshold ${threshold}`,
    }
  },

  async checkRequiredValidation(
    validated: boolean,
    field: string,
  ): Promise<{ passed: boolean; reason: string }> {
    return {
      passed: validated,
      reason: validated ? `${field} validation passed` : `${field} validation required but not completed`,
    }
  },

  async checkOrganizationalCompliance(
    constraints: string[],
    policies: string[],
  ): Promise<{ compliant: boolean; violations: string[] }> {
    const violations: string[] = []

    for (const constraint of constraints) {
      if (!policies.includes(constraint)) {
        violations.push(`Constraint "${constraint}" is not covered by any policy`)
      }
    }

    return {
      compliant: violations.length === 0,
      violations,
    }
  },

  async clearPolicies(): Promise<void> {
    policies.clear()
  },
}
