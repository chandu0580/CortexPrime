import type { EnterpriseDecisionResult } from "@/enterprise-decision/types"
import type { ExecutionAuthorization, ExecutionApproval, ReadinessCheck } from "./types"
import { generateId } from "./shared"

const approvalLevelRank: Record<string, number> = {
  none: 0,
  team: 1,
  management: 2,
  executive: 3,
}

export const AuthorizationEngine = {
  async evaluateAuthorization(result: EnterpriseDecisionResult): Promise<{
    authorization: ExecutionAuthorization
    approval: ExecutionApproval
    authorizationChecks: ReadinessCheck[]
  }> {
    const maxRequiredLevel = determineMaxRequiredLevel(result)
    const currentLevel = determineCurrentApprovalLevel(result)
    const authorized = approvalLevelRank[currentLevel] >= approvalLevelRank[maxRequiredLevel]

    const authorization: ExecutionAuthorization = {
      requiredLevel: maxRequiredLevel,
      currentLevel,
      authorized,
      grantedBy: currentLevel !== "none" ? "system" : null,
      grantedAt: currentLevel !== "none" ? new Date().toISOString() : null,
      expiresAt: currentLevel !== "none"
        ? new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString()
        : null,
    }

    const approvedOutcomes = result.outcomes.filter((o) => o.state === "approved")
    const allRequiredApprovalsMet = result.outcomes
      .filter((o) => o.approval.required)
      .every((o) => o.approval.approvedBy)

    const approval: ExecutionApproval = {
      required: result.outcomes.some((o) => o.approval.required),
      level: maxRequiredLevel,
      granted: allRequiredApprovalsMet && authorized,
      approvedBy: allRequiredApprovalsMet ? "system" : null,
      approvedAt: allRequiredApprovalsMet ? new Date().toISOString() : null,
      conditions: extractConditions(result),
      waiverGranted: false,
    }

    const authorizationChecks: ReadinessCheck[] = [
      {
        id: generateId("chk"),
        type: "authorization",
        name: "Authorization Level Check",
        description: "Current authorization must meet or exceed required level",
        result: authorized ? "pass" : "fail",
        details: `Required: ${maxRequiredLevel}, Current: ${currentLevel} — ${authorized ? "authorized" : "insufficient authorization"}`,
        sourceId: null,
        timestamp: new Date().toISOString(),
      },
      {
        id: generateId("chk"),
        type: "authorization",
        name: "Approval Completeness",
        description: "All required approvals must be granted",
        result: allRequiredApprovalsMet ? "pass" : "fail",
        details: allRequiredApprovalsMet
          ? "All required approvals obtained"
          : `${result.outcomes.filter((o) => o.approval.required && !o.approval.approvedBy).length} approvals pending`,
        sourceId: null,
        timestamp: new Date().toISOString(),
      },
      {
        id: generateId("chk"),
        type: "authorization",
        name: "Approved Outcomes Readiness",
        description: "Approved outcomes are ready for execution",
        result: approvedOutcomes.length > 0 ? "pass" : "info",
        details: `${approvedOutcomes.length} outcomes approved and ready`,
        sourceId: null,
        timestamp: new Date().toISOString(),
      },
    ]

    return { authorization, approval, authorizationChecks }
  },
}

function determineMaxRequiredLevel(result: EnterpriseDecisionResult): "none" | "team" | "management" | "executive" {
  const levels = result.outcomes.map((o) => o.approval.level)
  if (levels.includes("executive")) return "executive"
  if (levels.includes("management")) return "management"
  if (levels.includes("team")) return "team"
  return "none"
}

function determineCurrentApprovalLevel(result: EnterpriseDecisionResult): "none" | "team" | "management" | "executive" {
  const grantedLevels = result.outcomes
    .filter((o) => o.approval.approvedBy)
    .map((o) => o.approval.level)

  if (grantedLevels.includes("executive")) return "executive"
  if (grantedLevels.includes("management")) return "management"
  if (grantedLevels.includes("team")) return "team"
  return "none"
}

function extractConditions(result: EnterpriseDecisionResult): string[] {
  const conditions: string[] = []
  for (const outcome of result.outcomes) {
    for (const policy of outcome.policies) {
      if (policy.evaluation === "needs_review") {
        conditions.push(`${policy.name}: ${policy.details}`)
      }
    }
  }
  return [...new Set(conditions)]
}
