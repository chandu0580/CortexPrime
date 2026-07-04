import type { WorkerPolicy, WorkerPolicyRule, WorkerDecision } from "./types"
import { generateId } from "@/worker-framework/shared"

const policies = new Map<string, WorkerPolicy>()

export const WorkerPolicyEngine = {
  async createPolicy(policy: Omit<WorkerPolicy, "id">): Promise<WorkerPolicy> {
    const full: WorkerPolicy = { id: generateId("wo-policy"), ...policy }
    policies.set(full.id, full)
    return full
  },

  async getPolicy(policyId: string): Promise<WorkerPolicy | null> {
    return policies.get(policyId) ?? null
  },

  async getAllPolicies(): Promise<WorkerPolicy[]> {
    return Array.from(policies.values())
  },

  async getEnabledPolicies(): Promise<WorkerPolicy[]> {
    return Array.from(policies.values()).filter((p) => p.enabled)
  },

  async evaluatePolicies(workerId: string, action: string, context: Record<string, unknown>): Promise<WorkerPolicy[]> {
    const enabled = await this.getEnabledPolicies()
    const matched: WorkerPolicy[] = []

    for (const policy of enabled) {
      const pass = this.evaluatePolicy(policy, context)
      if (pass && policy.effect === "deny") {
        if (!matched.some((m) => m.id === policy.id)) matched.push(policy)
      }
    }

    return matched
  },

  async decide(workerId: string, action: string, context: Record<string, unknown>): Promise<WorkerDecision> {
    const matchedPolicies = await this.evaluatePolicies(workerId, action, context)

    let finalAction: WorkerDecision["action"] = "proceed"
    let reason = "No matching policies"

    if (matchedPolicies.length > 0) {
      finalAction = "terminate"
      reason = `Blocked by policies: ${matchedPolicies.map((p) => p.name).join(", ")}`
    }

    const decision: WorkerDecision = {
      id: generateId("wo-decision"),
      sessionId: (context.sessionId as string) ?? "",
      workerId,
      action: finalAction,
      reason,
      timestamp: new Date().toISOString(),
    }
    return decision
  },

  evaluatePolicy(policy: WorkerPolicy, context: Record<string, unknown>): boolean {
    for (const rule of policy.rules) {
      if (!this.evaluateRule(rule, context)) return false
    }
    return true
  },

  evaluateRule(rule: WorkerPolicyRule, context: Record<string, unknown>): boolean {
    const value = context[rule.field]

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
        return false
    }
  },
}
