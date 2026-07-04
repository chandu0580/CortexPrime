import type { IntegrationPolicy, IntegrationRule, IntegrationDecision, IntegrationResult } from "./types"
import { generateId } from "./shared"

const policies = new Map<string, IntegrationPolicy>()
const decisions = new Map<string, IntegrationDecision>()

export const IntegrationPolicyEngine = {
  async registerPolicy(policy: Omit<IntegrationPolicy, "id">): Promise<IntegrationPolicy> {
    const id = generateId("ipol")
    const full: IntegrationPolicy = { ...policy, id }
    policies.set(id, full)
    return full
  },

  async evaluateConnectorPolicy(policyId: string, state: string, requiredState: string): Promise<IntegrationDecision> {
    const policy = policies.get(policyId)
    if (!policy) throw new Error(`Policy not found: ${policyId}`)
    const passed = state === requiredState
    const decision: IntegrationDecision = {
      id: generateId("idec"),
      policyId,
      ruleId: "connector-state",
      action: passed ? "allow" : "deny",
      result: passed ? "success" : "failure",
      reason: passed ? `Connector state "${state}" matches required "${requiredState}"` : `Connector state "${state}" does not match required "${requiredState}"`,
      timestamp: new Date().toISOString(),
    }
    decisions.set(decision.id, decision)
    return decision
  },

  async evaluateEndpointPolicy(policyId: string, enabled: boolean, required: boolean): Promise<IntegrationDecision> {
    const policy = policies.get(policyId)
    if (!policy) throw new Error(`Policy not found: ${policyId}`)
    const passed = enabled === required
    const decision: IntegrationDecision = {
      id: generateId("idec"),
      policyId,
      ruleId: "endpoint-enabled",
      action: passed ? "allow" : "deny",
      result: passed ? "success" : "failure",
      reason: passed ? "Endpoint enabled state matches requirement" : "Endpoint enabled state does not match requirement",
      timestamp: new Date().toISOString(),
    }
    decisions.set(decision.id, decision)
    return decision
  },

  async evaluateSyncPolicy(policyId: string, jobCount: number, maxJobs: number): Promise<IntegrationDecision> {
    const policy = policies.get(policyId)
    if (!policy) throw new Error(`Policy not found: ${policyId}`)
    const passed = jobCount <= maxJobs
    const decision: IntegrationDecision = {
      id: generateId("idec"),
      policyId,
      ruleId: "sync-jobs",
      action: passed ? "allow" : "warn",
      result: passed ? "success" : "partial",
      reason: passed ? `Job count ${jobCount} within limit ${maxJobs}` : `Job count ${jobCount} exceeds limit ${maxJobs}`,
      timestamp: new Date().toISOString(),
    }
    decisions.set(decision.id, decision)
    return decision
  },

  async evaluateCredentialPolicy(policyId: string, valid: boolean): Promise<IntegrationDecision> {
    const policy = policies.get(policyId)
    if (!policy) throw new Error(`Policy not found: ${policyId}`)
    const decision: IntegrationDecision = {
      id: generateId("idec"),
      policyId,
      ruleId: "credential-valid",
      action: valid ? "allow" : "deny",
      result: valid ? "success" : "failure",
      reason: valid ? "Credential reference is valid" : "Credential reference is invalid",
      timestamp: new Date().toISOString(),
    }
    decisions.set(decision.id, decision)
    return decision
  },

  async evaluateRoutingPolicy(policyId: string, enabled: boolean): Promise<IntegrationDecision> {
    const policy = policies.get(policyId)
    if (!policy) throw new Error(`Policy not found: ${policyId}`)
    const decision: IntegrationDecision = {
      id: generateId("idec"),
      policyId,
      ruleId: "routing-enabled",
      action: enabled ? "allow" : "deny",
      result: enabled ? "success" : "failure",
      reason: enabled ? "Route is enabled" : "Route is disabled",
      timestamp: new Date().toISOString(),
    }
    decisions.set(decision.id, decision)
    return decision
  },

  async getPolicy(policyId: string): Promise<IntegrationPolicy | null> {
    return policies.get(policyId) ?? null
  },

  async listPolicies(): Promise<IntegrationPolicy[]> {
    return Array.from(policies.values())
  },

  async getDecisions(policyId?: string): Promise<IntegrationDecision[]> {
    let result = Array.from(decisions.values())
    if (policyId) result = result.filter((d) => d.policyId === policyId)
    return result.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
  },
}
