import type { PolicyEvaluation, PolicyResult, GovernancePolicy, PolicyRule } from "./types"
import { generateId } from "./shared"

const evaluations = new Map<string, PolicyEvaluation>()

export const PolicyEvaluationEngine = {
  async evaluatePolicy(policy: GovernancePolicy, sessionId: string, data: Record<string, unknown>): Promise<PolicyEvaluation[]> {
    if (!policy.enabled) return []

    const results: PolicyEvaluation[] = []

    for (const rule of policy.rules) {
      const result = await PolicyEvaluationEngine.evaluateRule(rule, policy.id, sessionId, data)
      results.push(result)
    }

    return results
  },

  async evaluatePolicies(policies: GovernancePolicy[], sessionId: string, data: Record<string, unknown>): Promise<PolicyEvaluation[]> {
    const allResults: PolicyEvaluation[] = []

    for (const policy of policies) {
      const results = await PolicyEvaluationEngine.evaluatePolicy(policy, sessionId, data)
      allResults.push(...results)
    }

    return allResults
  },

  async evaluateRule(rule: PolicyRule, policyId: string, sessionId: string, data: Record<string, unknown>): Promise<PolicyEvaluation> {
    const fieldValue = data[rule.field]
    let result: PolicyResult = "pass"
    let details = ""

    if (fieldValue === undefined) {
      result = "error"
      details = `Field "${rule.field}" not found in evaluation data`
    } else {
      result = PolicyEvaluationEngine.applyOperator(rule.operator, fieldValue, rule.value)
      details = `Evaluated ${rule.field} ${rule.operator} ${rule.value}: ${result}`
    }

    const evaluation: PolicyEvaluation = {
      id: generateId("eval"),
      policyId,
      ruleId: rule.id,
      sessionId,
      result,
      details,
      timestamp: new Date().toISOString(),
      metadata: { field: rule.field, operator: rule.operator, ruleEffect: rule.effect },
    }

    evaluations.set(evaluation.id, evaluation)
    return evaluation
  },

  applyOperator(operator: string, fieldValue: unknown, ruleValue: unknown): PolicyResult {
    switch (operator) {
      case "eq":
        return fieldValue === ruleValue ? "pass" : "fail"
      case "neq":
        return fieldValue !== ruleValue ? "pass" : "fail"
      case "gt":
        return typeof fieldValue === "number" && typeof ruleValue === "number" && fieldValue > ruleValue ? "pass" : "fail"
      case "gte":
        return typeof fieldValue === "number" && typeof ruleValue === "number" && fieldValue >= ruleValue ? "pass" : "fail"
      case "lt":
        return typeof fieldValue === "number" && typeof ruleValue === "number" && fieldValue < ruleValue ? "pass" : "fail"
      case "lte":
        return typeof fieldValue === "number" && typeof ruleValue === "number" && fieldValue <= ruleValue ? "pass" : "fail"
      case "in":
        return Array.isArray(ruleValue) && ruleValue.includes(fieldValue) ? "pass" : "fail"
      case "contains":
        return typeof fieldValue === "string" && typeof ruleValue === "string" && fieldValue.includes(ruleValue) ? "pass" : "fail"
      case "regex":
        try {
          return typeof fieldValue === "string" && typeof ruleValue === "string" && new RegExp(ruleValue).test(fieldValue) ? "pass" : "fail"
        } catch {
          return "error"
        }
      default:
        return "error"
    }
  },

  async explainDecision(evaluationId: string): Promise<{ evaluation: PolicyEvaluation; rule: PolicyRule | null; recommendation: string }> {
    const evaluation = evaluations.get(evaluationId)
    if (!evaluation) throw new Error(`Evaluation not found: ${evaluationId}`)
    return {
      evaluation,
      rule: null,
      recommendation: evaluation.result === "pass"
        ? "Allow: rule conditions are satisfied"
        : evaluation.result === "fail"
          ? "Deny: rule conditions not met"
          : "Review: evaluation encountered an issue",
    }
  },

  async getEvaluations(sessionId?: string): Promise<PolicyEvaluation[]> {
    let result = Array.from(evaluations.values())
    if (sessionId) result = result.filter((e) => e.sessionId === sessionId)
    return result.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
  },

  async getEvaluationCount(): Promise<number> {
    return evaluations.size
  },
}
