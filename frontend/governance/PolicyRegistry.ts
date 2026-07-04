import type { GovernancePolicy, PolicyRule } from "./types"
import { generateId } from "./shared"

const policies = new Map<string, GovernancePolicy>()

export const PolicyRegistry = {
  async registerPolicy(
    name: string,
    description: string,
    category: string,
    rules: PolicyRule[],
    version: string = "1.0.0",
    priority: number = 100,
    tags: Record<string, string> = {},
  ): Promise<GovernancePolicy> {
    if (Array.from(policies.values()).some((p) => p.name === name)) {
      throw new Error(`Policy already registered: ${name}`)
    }
    const id = generateId("policy")
    const now = new Date().toISOString()
    const policy: GovernancePolicy = {
      id,
      name,
      description,
      category,
      version,
      enabled: true,
      priority,
      rules,
      tags,
      createdAt: now,
      updatedAt: now,
    }
    policies.set(id, policy)
    return policy
  },

  async unregisterPolicy(policyId: string): Promise<void> {
    if (!policies.has(policyId)) throw new Error(`Policy not found: ${policyId}`)
    policies.delete(policyId)
  },

  async getPolicy(policyId: string): Promise<GovernancePolicy | null> {
    return policies.get(policyId) ?? null
  },

  async listPolicies(category?: string): Promise<GovernancePolicy[]> {
    let result = Array.from(policies.values())
    if (category) result = result.filter((p) => p.category === category)
    return result.sort((a, b) => a.priority - b.priority)
  },

  async enablePolicy(policyId: string): Promise<GovernancePolicy> {
    const policy = policies.get(policyId)
    if (!policy) throw new Error(`Policy not found: ${policyId}`)
    const updated: GovernancePolicy = { ...policy, enabled: true, updatedAt: new Date().toISOString() }
    policies.set(policyId, updated)
    return updated
  },

  async disablePolicy(policyId: string): Promise<GovernancePolicy> {
    const policy = policies.get(policyId)
    if (!policy) throw new Error(`Policy not found: ${policyId}`)
    const updated: GovernancePolicy = { ...policy, enabled: false, updatedAt: new Date().toISOString() }
    policies.set(policyId, updated)
    return updated
  },

  async updatePolicy(policyId: string, updates: Partial<GovernancePolicy>): Promise<GovernancePolicy> {
    const policy = policies.get(policyId)
    if (!policy) throw new Error(`Policy not found: ${policyId}`)
    const updated: GovernancePolicy = { ...policy, ...updates, id: policyId, updatedAt: new Date().toISOString() }
    policies.set(policyId, updated)
    return updated
  },

  async policyCount(): Promise<number> {
    return policies.size
  },
}
