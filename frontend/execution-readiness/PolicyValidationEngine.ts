import type { EnterpriseDecisionResult } from "@/enterprise-decision/types"
import type { ReadinessCheck, ReadinessPolicy, ReadinessResult } from "./types"
import { generateId } from "./shared"

const readinessPolicies: {
  name: string
  category: string
  evaluate: (result: EnterpriseDecisionResult) => ReadinessResult
  details: (result: EnterpriseDecisionResult) => string
}[] = [
  {
    name: "All Decisions Resolved",
    category: "Completeness",
    evaluate: (r) => {
      const unresolved = r.outcomes.filter((o) => o.state === "draft" || o.state === "pending_approval")
      return unresolved.length === 0 ? "pass" : "fail"
    },
    details: (r) => {
      const unresolved = r.outcomes.filter((o) => o.state === "draft" || o.state === "pending_approval")
      return unresolved.length === 0
        ? "All decisions are in a terminal state"
        : `${unresolved.length} decisions still in draft or pending_approval state`
    },
  },
  {
    name: "No Rejected Decisions",
    category: "Quality",
    evaluate: (r) => {
      const rejected = r.outcomes.filter((o) => o.state === "rejected")
      return rejected.length === 0 ? "pass" : "fail"
    },
    details: (r) => {
      const rejected = r.outcomes.filter((o) => o.state === "rejected")
      return rejected.length === 0
        ? "No rejected decisions"
        : `${rejected.length} decisions were rejected and must be revised`
    },
  },
  {
    name: "Approval Completeness",
    category: "Governance",
    evaluate: (r) => {
      const pendingApproval = r.outcomes.filter((o) => o.approval.required && !o.approval.approvedBy)
      return pendingApproval.length === 0 ? "pass" : "warning"
    },
    details: (r) => {
      const pendingApproval = r.outcomes.filter((o) => o.approval.required && !o.approval.approvedBy)
      return pendingApproval.length === 0
        ? "All required approvals obtained"
        : `${pendingApproval.length} outcomes still require approval`
    },
  },
  {
    name: "Escalation Resolution",
    category: "Governance",
    evaluate: (r) => {
      const escalated = r.outcomes.filter((o) => o.escalation.required)
      return escalated.length === 0 ? "pass" : "warning"
    },
    details: (r) => {
      const escalated = r.outcomes.filter((o) => o.escalation.required)
      return escalated.length === 0
        ? "No escalations required"
        : `${escalated.length} outcomes require escalation resolution before execution`
    },
  },
  {
    name: "Policy Compliance",
    category: "Compliance",
    evaluate: (r) => {
      const failedPolicies = r.outcomes.filter((o) => o.policies.some((p) => p.evaluation === "failed"))
      return failedPolicies.length === 0 ? "pass" : "fail"
    },
    details: (r) => {
      const failedPolicies = r.outcomes.filter((o) => o.policies.some((p) => p.evaluation === "failed"))
      return failedPolicies.length === 0
        ? "All policy evaluations passed"
        : `${failedPolicies.length} outcomes have failed policy evaluations`
    },
  },
  {
    name: "State Distribution Balance",
    category: "Readiness",
    evaluate: (r) => {
      const ready = r.stateCounts.approved ?? 0
      const total = r.outcomes.length
      return total > 0 && ready / total >= 0.5 ? "pass" : "warning"
    },
    details: (r) => {
      const ready = r.stateCounts.approved ?? 0
      const total = r.outcomes.length
      return `${ready}/${total} outcomes approved for execution (${((ready / total) * 100).toFixed(0)}%)`
    },
  },
]

export const PolicyValidationEngine = {
  async validatePolicies(result: EnterpriseDecisionResult): Promise<{
    policyChecks: ReadinessCheck[]
    policies: ReadinessPolicy[]
  }> {
    const policies: ReadinessPolicy[] = readinessPolicies.map((def) => ({
      id: generateId("policy"),
      name: def.name,
      category: def.category,
      evaluation: def.evaluate(result),
      details: def.details(result),
    }))

    const failedPolicies = policies.filter((p) => p.evaluation === "fail")
    const warningPolicies = policies.filter((p) => p.evaluation === "warning")

    const policyChecks: ReadinessCheck[] = [
      {
        id: generateId("chk"),
        type: "policy",
        name: "Policy Validation Summary",
        description: "All readiness policies must pass for GO decision",
        result: failedPolicies.length === 0 ? (warningPolicies.length === 0 ? "pass" : "warning") : "fail",
        details: `${policies.length} policies evaluated: ${policies.filter((p) => p.evaluation === "pass").length} pass, ${warningPolicies.length} warnings, ${failedPolicies.length} failed`,
        sourceId: null,
        timestamp: new Date().toISOString(),
      },
      {
        id: generateId("chk"),
        type: "policy",
        name: "Critical Policy Compliance",
        description: "Policies in Governance and Compliance categories must pass",
        result: failedPolicies.filter((p) => p.category === "Compliance" || p.category === "Governance").length === 0 ? "pass" : "fail",
        details: "All governance and compliance policies are satisfied",
        sourceId: null,
        timestamp: new Date().toISOString(),
      },
    ]

    return { policyChecks, policies }
  },
}
