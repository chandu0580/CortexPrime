import type { ComplianceResult, ComplianceState, GovernanceViolation, GovernancePolicy, PolicyEvaluation } from "./types"
import { generateId } from "./shared"

const complianceResults = new Map<string, ComplianceResult>()
const violations = new Map<string, GovernanceViolation>()

export const ComplianceEngine = {
  async validateCompliance(sessionId: string, policy: GovernancePolicy, evaluations: PolicyEvaluation[]): Promise<ComplianceResult> {
    const failedEvaluations = evaluations.filter((e) => e.result === "fail")
    const warnings = evaluations.filter((e) => e.result === "review").map((e) => e.details)

    let state: ComplianceState
    if (failedEvaluations.length === 0 && warnings.length === 0) {
      state = "compliant"
    } else if (failedEvaluations.length > 0) {
      state = "non_compliant"
    } else {
      state = "pending"
    }

    const result: ComplianceResult = {
      id: generateId("comp"),
      sessionId,
      policyId: policy.id,
      state,
      violations: failedEvaluations.map((e) => `Rule ${e.ruleId}: ${e.details}`),
      warnings,
      checkedAt: new Date().toISOString(),
      details: {
        totalEvaluations: evaluations.length,
        passed: evaluations.filter((e) => e.result === "pass").length,
        failed: failedEvaluations.length,
        reviewed: warnings.length,
      },
    }

    complianceResults.set(result.id, result)

    for (const failed of failedEvaluations) {
      await ComplianceEngine.recordViolation(sessionId, policy.id, failed.ruleId, "high", failed.details)
    }

    return result
  },

  async detectViolations(sessionId: string, policyId: string): Promise<GovernanceViolation[]> {
    return Array.from(violations.values()).filter(
      (v) => v.sessionId === sessionId && v.policyId === policyId,
    )
  },

  async recordViolation(sessionId: string, policyId: string, ruleId: string, severity: "low" | "medium" | "high" | "critical", message: string): Promise<GovernanceViolation> {
    const violation: GovernanceViolation = {
      id: generateId("viol"),
      sessionId,
      policyId,
      ruleId,
      severity,
      message,
      timestamp: new Date().toISOString(),
      resolved: false,
      resolvedAt: null,
    }
    violations.set(violation.id, violation)
    return violation
  },

  async resolveViolation(violationId: string): Promise<GovernanceViolation> {
    const violation = violations.get(violationId)
    if (!violation) throw new Error(`Violation not found: ${violationId}`)
    const updated: GovernanceViolation = {
      ...violation,
      resolved: true,
      resolvedAt: new Date().toISOString(),
    }
    violations.set(violationId, updated)
    return updated
  },

  async generateComplianceReport(sessionId: string): Promise<{ results: ComplianceResult[]; violations: GovernanceViolation[]; summary: string }> {
    const results = Array.from(complianceResults.values()).filter((r) => r.sessionId === sessionId)
    const sessionViolations = Array.from(violations.values()).filter((v) => v.sessionId === sessionId)
    const compliant = results.filter((r) => r.state === "compliant").length
    const total = results.length
    const summary = total === 0
      ? "No compliance checks performed"
      : `${compliant}/${total} compliance checks passed, ${sessionViolations.length} violations detected`
    return { results, violations: sessionViolations, summary }
  },

  async getComplianceResult(id: string): Promise<ComplianceResult | null> {
    return complianceResults.get(id) ?? null
  },

  async getViolationCount(): Promise<number> {
    return violations.size
  },
}
