import type { AnalyticsPolicy, AnalyticsDecision, AnalyticsResult } from "./types"
import { generateId } from "./shared"

const policies = new Map<string, AnalyticsPolicy>()
const decisions = new Map<string, AnalyticsDecision>()

export const AnalyticsPolicyEngine = {
  async registerPolicy(policy: Omit<AnalyticsPolicy, "id">): Promise<AnalyticsPolicy> {
    const id = generateId("apol")
    const full: AnalyticsPolicy = { ...policy, id }
    policies.set(id, full)
    return full
  },

  async evaluateAggregationPolicy(policyId: string, metricCount: number, maxMetrics: number): Promise<AnalyticsDecision> {
    const policy = policies.get(policyId)
    if (!policy) throw new Error(`Policy not found: ${policyId}`)
    const passed = metricCount <= maxMetrics
    const decision: AnalyticsDecision = {
      id: generateId("adec"),
      sessionId: "",
      policyId,
      action: passed ? "allow" : "truncate",
      result: passed ? "success" : "partial",
      reason: passed ? `Metric count ${metricCount} within limit ${maxMetrics}` : `Metric count ${metricCount} exceeds limit ${maxMetrics}`,
      timestamp: new Date().toISOString(),
    }
    decisions.set(decision.id, decision)
    return decision
  },

  async evaluateKPIPolicy(policyId: string, kpiCount: number, maxKPIs: number): Promise<AnalyticsDecision> {
    const policy = policies.get(policyId)
    if (!policy) throw new Error(`Policy not found: ${policyId}`)
    const passed = kpiCount <= maxKPIs
    const decision: AnalyticsDecision = {
      id: generateId("adec"),
      sessionId: "",
      policyId,
      action: passed ? "allow" : "prune",
      result: passed ? "success" : "partial",
      reason: passed ? `KPI count ${kpiCount} within limit ${maxKPIs}` : `KPI count ${kpiCount} exceeds limit ${maxKPIs}`,
      timestamp: new Date().toISOString(),
    }
    decisions.set(decision.id, decision)
    return decision
  },

  async evaluateReportingPolicy(policyId: string, sectionCount: number, maxSections: number): Promise<AnalyticsDecision> {
    const policy = policies.get(policyId)
    if (!policy) throw new Error(`Policy not found: ${policyId}`)
    const passed = sectionCount <= maxSections
    const decision: AnalyticsDecision = {
      id: generateId("adec"),
      sessionId: "",
      policyId,
      action: passed ? "allow" : "consolidate",
      result: passed ? "success" : "partial",
      reason: passed ? `Section count ${sectionCount} within limit ${maxSections}` : `Section count ${sectionCount} exceeds limit ${maxSections}`,
      timestamp: new Date().toISOString(),
    }
    decisions.set(decision.id, decision)
    return decision
  },

  async evaluateForecastingPolicy(policyId: string, dataPoints: number, maxPoints: number): Promise<AnalyticsDecision> {
    const policy = policies.get(policyId)
    if (!policy) throw new Error(`Policy not found: ${policyId}`)
    const passed = dataPoints <= maxPoints
    const decision: AnalyticsDecision = {
      id: generateId("adec"),
      sessionId: "",
      policyId,
      action: passed ? "allow" : "sample",
      result: passed ? "success" : "partial",
      reason: passed ? `Data points ${dataPoints} within limit ${maxPoints}` : `Data points ${dataPoints} exceeds limit ${maxPoints}`,
      timestamp: new Date().toISOString(),
    }
    decisions.set(decision.id, decision)
    return decision
  },

  async evaluateInsightPolicy(policyId: string, insightCount: number, maxInsights: number): Promise<AnalyticsDecision> {
    const policy = policies.get(policyId)
    if (!policy) throw new Error(`Policy not found: ${policyId}`)
    const passed = insightCount <= maxInsights
    const decision: AnalyticsDecision = {
      id: generateId("adec"),
      sessionId: "",
      policyId,
      action: passed ? "allow" : "throttle",
      result: passed ? "success" : "partial",
      reason: passed ? `Insight count ${insightCount} within limit ${maxInsights}` : `Insight count ${insightCount} exceeds limit ${maxInsights}`,
      timestamp: new Date().toISOString(),
    }
    decisions.set(decision.id, decision)
    return decision
  },

  async getPolicy(policyId: string): Promise<AnalyticsPolicy | null> {
    return policies.get(policyId) ?? null
  },

  async listPolicies(): Promise<AnalyticsPolicy[]> {
    return Array.from(policies.values())
  },

  async getDecisions(policyId?: string): Promise<AnalyticsDecision[]> {
    let result = Array.from(decisions.values())
    if (policyId) result = result.filter((d) => d.policyId === policyId)
    return result.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
  },
}
