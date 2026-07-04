import type { EnterpriseDecision } from "@/enterprise-reasoning/types"
import type { DecisionPolicy, DecisionEscalation } from "./types"

export const EscalationEngine = {
  async evaluate(decision: EnterpriseDecision, policies: DecisionPolicy[]): Promise<DecisionEscalation> {
    const failedPolicies = policies.filter((p) => p.evaluation === "failed")
    const reviewPolicies = policies.filter((p) => p.evaluation === "needs_review")
    const isCriticalRisk = decision.category === "risk" && decision.confidence.score < 0.6

    let required = false
    let reason = ""
    let targetLevel = ""
    let triggeredBy = ""

    if (failedPolicies.length >= 2) {
      required = true
      reason = `Multiple policy failures: ${failedPolicies.map((p) => p.name).join(", ")}`
      targetLevel = "executive_sponsor"
      triggeredBy = "PolicyEvaluationEngine"
    } else if (isCriticalRisk) {
      required = true
      reason = "Critical risk decision requires immediate senior attention"
      targetLevel = "risk_committee"
      triggeredBy = "EscalationEngine"
    } else if (reviewPolicies.length >= 2 && decision.category !== "strategy") {
      required = true
      reason = `Multiple policy flags require management review: ${reviewPolicies.map((p) => p.name).join(", ")}`
      targetLevel = "department_head"
      triggeredBy = "EscalationEngine"
    }

    return { required, reason, targetLevel, triggeredBy }
  },
}
