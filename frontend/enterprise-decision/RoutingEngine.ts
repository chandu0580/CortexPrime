import type { EnterpriseDecision } from "@/enterprise-reasoning/types"
import type { DecisionPolicy, DecisionApproval, DecisionEscalation, DecisionRoute, DecisionState } from "./types"
import type { MissionIntelligenceReport } from "@/mission-intelligence/types"

export const RoutingEngine = {
  async evaluate(
    decision: EnterpriseDecision,
    policies: DecisionPolicy[],
    approval: DecisionApproval,
    escalation: DecisionEscalation,
    report: MissionIntelligenceReport,
  ): Promise<{ state: DecisionState; route: DecisionRoute }> {
    const hasCriticalRisk = report.risks.some((r) => r.impact === "critical")
    const hasFailedPolicies = policies.some((p) => p.evaluation === "failed")
    const lowConfidence = decision.confidence.score < 0.5
    const needsExecutiveApproval = approval.level === "executive"

    if (hasCriticalRisk) {
      return {
        state: "needs_review",
        route: {
          target: "intervention",
          reason: "Critical risk identified in risk assessment — requires intervention workspace review",
          priority: "critical",
        },
      }
    }

    if (hasFailedPolicies && lowConfidence) {
      return {
        state: "rejected",
        route: {
          target: "mission_revision",
          reason: `Decision failed policy evaluation and has low confidence (${(decision.confidence.score * 100).toFixed(0)}%) — requires mission revision`,
          priority: "high",
        },
      }
    }

    if (hasFailedPolicies) {
      return {
        state: "needs_review",
        route: {
          target: "review",
          reason: `Decision requires review due to failed policy evaluations: ${policies.filter((p) => p.evaluation === "failed").map((p) => p.name).join(", ")}`,
          priority: "high",
        },
      }
    }

    if (needsExecutiveApproval) {
      return {
        state: "pending_approval",
        route: {
          target: "review",
          reason: "Executive approval required before this decision can proceed",
          priority: "medium",
        },
      }
    }

    if (escalation.required) {
      return {
        state: "escalated",
        route: {
          target: "review",
          reason: escalation.reason,
          priority: "high",
        },
      }
    }

    if (approval.required && approval.level === "management") {
      return {
        state: "pending_approval",
        route: {
          target: "review",
          reason: `Management approval required (level: ${approval.level})`,
          priority: "medium",
        },
      }
    }

    if (decision.category === "risk" && decision.confidence.score < 0.7) {
      return {
        state: "deferred",
        route: {
          target: "learning",
          reason: "Risk decision confidence below threshold — deferred to learning queue for additional analysis",
          priority: "low",
        },
      }
    }

    return {
      state: "approved",
      route: {
        target: "runtime",
        reason: "All checks passed — decision approved for runtime execution",
        priority: "medium",
      },
    }
  },
}
