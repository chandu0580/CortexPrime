import type { CapabilityPolicy, PolicyEffect, CapabilityDefinition } from "./types"
import { CapabilityRegistry } from "./CapabilityRegistry"

interface PolicyEvaluation {
  policy: CapabilityPolicy
  matched: boolean
  effect: PolicyEffect | null
  reason: string | null
}

export const CapabilityPolicyManager = {
  async evaluate(capabilityId: string, resource: string, action: string, context: Record<string, unknown>): Promise<PolicyEvaluation[]> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }

    const evaluations: PolicyEvaluation[] = []

    for (const policy of definition.policies) {
      if (!policy.enabled) {
        evaluations.push({
          policy,
          matched: false,
          effect: null,
          reason: "Policy is disabled",
        })
        continue
      }

      if (!this.resourceMatches(policy.resource, resource)) {
        evaluations.push({
          policy,
          matched: false,
          effect: null,
          reason: `Resource "${resource}" does not match policy resource "${policy.resource}"`,
        })
        continue
      }

      if (!this.actionMatches(policy.actions, action)) {
        evaluations.push({
          policy,
          matched: false,
          effect: null,
          reason: `Action "${action}" is not in policy actions [${policy.actions.join(", ")}]`,
        })
        continue
      }

      const conditionResult = this.evaluateConditions(policy.conditions, context)
      if (!conditionResult.matched) {
        evaluations.push({
          policy,
          matched: false,
          effect: null,
          reason: conditionResult.reason,
        })
        continue
      }

      evaluations.push({
        policy,
        matched: true,
        effect: policy.effect,
        reason: null,
      })
    }

    return evaluations
  },

  async getEffectiveAllowList(capabilityId: string): Promise<string[]> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }

    const allowed: string[] = []
    const denied: string[] = []

    for (const policy of definition.policies.sort((a, b) => b.priority - a.priority)) {
      if (!policy.enabled) continue

      for (const action of policy.actions) {
        if (policy.effect === "allow" && !denied.includes(action)) {
          if (!allowed.includes(action)) allowed.push(action)
        } else if (policy.effect === "deny") {
          if (!denied.includes(action)) denied.push(action)
          const idx = allowed.indexOf(action)
          if (idx !== -1) allowed.splice(idx, 1)
        }
      }
    }

    return allowed
  },

  async addPolicy(capabilityId: string, policy: CapabilityPolicy): Promise<void> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }
    definition.policies.push(policy)
    definition.policies.sort((a, b) => b.priority - a.priority)
    definition.updatedAt = new Date().toISOString()
  },

  async removePolicy(capabilityId: string, policyId: string): Promise<void> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }
    const index = definition.policies.findIndex((p) => p.id === policyId)
    if (index === -1) {
      throw new Error(`Policy ${policyId} not found in capability ${capabilityId}`)
    }
    definition.policies.splice(index, 1)
    definition.updatedAt = new Date().toISOString()
  },

  resourceMatches(policyResource: string, resource: string): boolean {
    if (policyResource === "*") return true
    if (policyResource === resource) return true

    const pattern = policyResource.replace(/\*/g, ".*")
    return new RegExp(`^${pattern}$`).test(resource)
  },

  actionMatches(policyActions: string[], action: string): boolean {
    if (policyActions.includes("*")) return true
    return policyActions.some((pa) => {
      const pattern = pa.replace(/\*/g, ".*")
      return new RegExp(`^${pattern}$`).test(action)
    })
  },

  evaluateConditions(conditions: Record<string, unknown>, context: Record<string, unknown>): { matched: boolean; reason: string | null } {
    for (const [key, expected] of Object.entries(conditions)) {
      const actual = context[key]
      if (actual === undefined) {
        return { matched: false, reason: `Context missing required condition key: ${key}` }
      }
      if (String(actual) !== String(expected)) {
        return { matched: false, reason: `Condition "${key}": expected "${String(expected)}", got "${String(actual)}"` }
      }
    }
    return { matched: true, reason: null }
  },
}
