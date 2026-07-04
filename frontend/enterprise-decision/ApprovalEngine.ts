import type { EnterpriseDecision } from "@/enterprise-reasoning/types"
import type { DecisionPolicy, DecisionApproval, ApprovalLevel } from "./types"

function determineApprovalLevel(decision: EnterpriseDecision, policies: DecisionPolicy[]): ApprovalLevel {
  const hasFailedPolicies = policies.some((p) => p.evaluation === "failed")
  const hasReviewPolicies = policies.some((p) => p.evaluation === "needs_review")
  const isHighRisk = decision.category === "risk"
  const isStrategy = decision.category === "strategy"

  if (isStrategy || hasFailedPolicies) return "executive"
  if (isHighRisk || hasReviewPolicies) return "management"
  if (decision.confidence.score >= 0.85) return "none"
  return "team"
}

function buildConditions(decision: EnterpriseDecision, policies: DecisionPolicy[]): string[] {
  const conditions: string[] = []

  if (policies.some((p) => p.evaluation === "failed")) {
    conditions.push("Address all failed policy evaluations before approval")
  }
  if (policies.some((p) => p.evaluation === "needs_review")) {
    conditions.push("Review and resolve policy flags before final approval")
  }
  if (decision.alternatives.length > 0) {
    conditions.push("Document rationale for selected alternative over evaluated options")
  }
  if (decision.confidence.score < 0.7) {
    conditions.push("Improve decision confidence through additional evidence gathering")
  }

  return conditions
}

export const ApprovalEngine = {
  async evaluate(decision: EnterpriseDecision, policies: DecisionPolicy[]): Promise<DecisionApproval> {
    const level = determineApprovalLevel(decision, policies)

    return {
      required: level !== "none",
      level,
      approvedBy: null,
      approvedAt: null,
      conditions: buildConditions(decision, policies),
    }
  },
}
