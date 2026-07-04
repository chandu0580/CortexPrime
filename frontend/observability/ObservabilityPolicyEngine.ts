import type { ObservabilityPolicy, ObservabilityDecision } from "./types"
import { generateId } from "./shared"

const policies = new Map<string, ObservabilityPolicy>()
const decisions = new Map<string, ObservabilityDecision>()

export const ObservabilityPolicyEngine = {
  async registerPolicy(policy: Omit<ObservabilityPolicy, "id">): Promise<ObservabilityPolicy> {
    const id = generateId("policy")
    const full: ObservabilityPolicy = { ...policy, id }
    policies.set(id, full)
    return full
  },

  async evaluateAuditRetention(policyId: string, auditAgeMs: number, maxRetentionMs: number): Promise<ObservabilityDecision> {
    const policy = policies.get(policyId)
    if (!policy) throw new Error(`Policy not found: ${policyId}`)
    const shouldRetain = auditAgeMs <= maxRetentionMs
    const decision: ObservabilityDecision = {
      id: generateId("decision"),
      policyId,
      action: shouldRetain ? "retain" : "expire",
      reason: shouldRetain
        ? `Audit age ${auditAgeMs}ms within retention limit ${maxRetentionMs}ms`
        : `Audit age ${auditAgeMs}ms exceeds retention limit ${maxRetentionMs}ms`,
      timestamp: new Date().toISOString(),
    }
    decisions.set(decision.id, decision)
    return decision
  },

  async evaluateTracePolicy(policyId: string, spanCount: number, maxSpans: number): Promise<ObservabilityDecision> {
    const policy = policies.get(policyId)
    if (!policy) throw new Error(`Policy not found: ${policyId}`)
    const isCompliant = spanCount <= maxSpans
    const decision: ObservabilityDecision = {
      id: generateId("decision"),
      policyId,
      action: isCompliant ? "allow" : "warn",
      reason: isCompliant
        ? `Trace span count ${spanCount} within limit ${maxSpans}`
        : `Trace span count ${spanCount} exceeds limit ${maxSpans}`,
      timestamp: new Date().toISOString(),
    }
    decisions.set(decision.id, decision)
    return decision
  },

  async evaluateReplayPolicy(policyId: string, frameCount: number, maxFrames: number): Promise<ObservabilityDecision> {
    const policy = policies.get(policyId)
    if (!policy) throw new Error(`Policy not found: ${policyId}`)
    const isCompliant = frameCount <= maxFrames
    const decision: ObservabilityDecision = {
      id: generateId("decision"),
      policyId,
      action: isCompliant ? "allow" : "reject",
      reason: isCompliant
        ? `Replay frame count ${frameCount} within limit ${maxFrames}`
        : `Replay frame count ${frameCount} exceeds limit ${maxFrames}`,
      timestamp: new Date().toISOString(),
    }
    decisions.set(decision.id, decision)
    return decision
  },

  async evaluateMetricsPolicy(policyId: string, sampleCount: number, maxSamples: number): Promise<ObservabilityDecision> {
    const policy = policies.get(policyId)
    if (!policy) throw new Error(`Policy not found: ${policyId}`)
    const isCompliant = sampleCount <= maxSamples
    const decision: ObservabilityDecision = {
      id: generateId("decision"),
      policyId,
      action: isCompliant ? "allow" : "truncate",
      reason: isCompliant
        ? `Metric sample count ${sampleCount} within limit ${maxSamples}`
        : `Metric sample count ${sampleCount} exceeds limit ${maxSamples}`,
      timestamp: new Date().toISOString(),
    }
    decisions.set(decision.id, decision)
    return decision
  },

  async evaluateDiagnosticPolicy(policyId: string, diagnosticCount: number, maxDiagnostics: number): Promise<ObservabilityDecision> {
    const policy = policies.get(policyId)
    if (!policy) throw new Error(`Policy not found: ${policyId}`)
    const isCompliant = diagnosticCount <= maxDiagnostics
    const decision: ObservabilityDecision = {
      id: generateId("decision"),
      policyId,
      action: isCompliant ? "allow" : "throttle",
      reason: isCompliant
        ? `Diagnostic count ${diagnosticCount} within limit ${maxDiagnostics}`
        : `Diagnostic count ${diagnosticCount} exceeds limit ${maxDiagnostics}`,
      timestamp: new Date().toISOString(),
    }
    decisions.set(decision.id, decision)
    return decision
  },

  async getPolicy(policyId: string): Promise<ObservabilityPolicy | null> {
    return policies.get(policyId) ?? null
  },

  async listPolicies(): Promise<ObservabilityPolicy[]> {
    return Array.from(policies.values())
  },

  async getDecisions(policyId?: string): Promise<ObservabilityDecision[]> {
    let result = Array.from(decisions.values())
    if (policyId) result = result.filter((d) => d.policyId === policyId)
    return result.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
  },
}
