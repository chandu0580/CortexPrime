import type { CoordinationPolicy } from "./types"
import { generateId } from "./shared"

const policies = new Map<string, CoordinationPolicy>()

export const CoordinationPolicyEngine = {
  async registerPolicy(policy: Omit<CoordinationPolicy, "id">): Promise<CoordinationPolicy> {
    const id = generateId("cpol")
    const full: CoordinationPolicy = { ...policy, id }
    policies.set(id, full)
    return full
  },

  async evaluateDelegationPolicy(policyId: string, workerLoad: number, maxLoad: number): Promise<{ passed: boolean; reason: string }> {
    const policy = policies.get(policyId)
    if (!policy) throw new Error(`Policy not found: ${policyId}`)
    const passed = workerLoad <= maxLoad
    return {
      passed,
      reason: passed ? `Worker load ${workerLoad} within limit ${maxLoad}` : `Worker load ${workerLoad} exceeds limit ${maxLoad}`,
    }
  },

  async evaluateRoutingPolicy(policyId: string, availableWorkers: number, minRequired: number): Promise<{ passed: boolean; reason: string }> {
    const policy = policies.get(policyId)
    if (!policy) throw new Error(`Policy not found: ${policyId}`)
    const passed = availableWorkers >= minRequired
    return {
      passed,
      reason: passed ? `${availableWorkers} workers available, meets minimum ${minRequired}` : `Only ${availableWorkers} workers available, need ${minRequired}`,
    }
  },

  async evaluateSyncPolicy(policyId: string, barriersWaiting: number, maxWaitTime: number): Promise<{ passed: boolean; reason: string }> {
    const policy = policies.get(policyId)
    if (!policy) throw new Error(`Policy not found: ${policyId}`)
    const passed = barriersWaiting <= maxWaitTime
    return {
      passed,
      reason: passed ? `${barriersWaiting} barriers waiting, within threshold ${maxWaitTime}` : `${barriersWaiting} barriers waiting, exceeds threshold ${maxWaitTime}`,
    }
  },

  async evaluateWorkerAvailabilityPolicy(policyId: string, availableCount: number, totalCount: number): Promise<{ passed: boolean; reason: string }> {
    const policy = policies.get(policyId)
    if (!policy) throw new Error(`Policy not found: ${policyId}`)
    const ratio = totalCount === 0 ? 0 : availableCount / totalCount
    const passed = ratio >= 0.5
    return {
      passed,
      reason: passed ? `${(ratio * 100).toFixed(0)}% workers available, above 50% threshold` : `Only ${(ratio * 100).toFixed(0)}% workers available, below 50% threshold`,
    }
  },

  async evaluateExecutionOrderingPolicy(policyId: string, sequenceValid: boolean, dependenciesMet: boolean): Promise<{ passed: boolean; reason: string }> {
    const policy = policies.get(policyId)
    if (!policy) throw new Error(`Policy not found: ${policyId}`)
    const passed = sequenceValid && dependenciesMet
    return {
      passed,
      reason: passed ? "Execution ordering is valid and all dependencies are met" : "Execution ordering is invalid or dependencies not met",
    }
  },

  async getPolicy(policyId: string): Promise<CoordinationPolicy | null> {
    return policies.get(policyId) ?? null
  },

  async listPolicies(): Promise<CoordinationPolicy[]> {
    return Array.from(policies.values())
  },
}
