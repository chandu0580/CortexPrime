import type { EnterpriseReasoningReport } from "@/enterprise-reasoning/types"
import type { EnterpriseDecisionResult, DecisionOutcome, DecisionAction, AuditEvent, DecisionState } from "./types"
import { generateId } from "./shared"
import { PolicyEvaluationEngine } from "./PolicyEvaluationEngine"
import { ApprovalEngine } from "./ApprovalEngine"
import { EscalationEngine } from "./EscalationEngine"
import { RoutingEngine } from "./RoutingEngine"
import { DecisionAuditBuilder } from "./DecisionAuditBuilder"

function generateActions(): DecisionAction[] {
  return [
    { id: generateId("action"), type: "document", description: "Document decision rationale and outcomes", assignedTo: "Decision Owner", deadline: "Within planning phase" },
    { id: generateId("action"), type: "communicate", description: "Communicate decision to relevant stakeholders", assignedTo: "Project Manager", deadline: "Within 3 business days" },
    { id: generateId("action"), type: "track", description: "Add decision tracking entry to mission plan", assignedTo: "Technical Lead", deadline: "Within planning phase" },
  ]
}

export const enterpriseDecisionEngine = {
  async evaluate(report: EnterpriseReasoningReport): Promise<EnterpriseDecisionResult> {
    const outcomes: DecisionOutcome[] = []
    const allEvents: AuditEvent[] = []

    for (const decision of report.decisions) {
      const policies = await PolicyEvaluationEngine.evaluate(decision)
      const approval = await ApprovalEngine.evaluate(decision, policies)
      const escalation = await EscalationEngine.evaluate(decision, policies)
      const { state, route } = await RoutingEngine.evaluate(decision, policies, approval, escalation, report as unknown as import("@/mission-intelligence/types").MissionIntelligenceReport)

      allEvents.push(
        { id: generateId("event"), timestamp: new Date().toISOString(), actor: "PolicyEvaluationEngine", action: "policy_evaluation", details: `${policies.length} policies evaluated, ${policies.filter((p) => p.evaluation === "passed").length} passed` },
        { id: generateId("event"), timestamp: new Date().toISOString(), actor: "ApprovalEngine", action: "approval_evaluation", details: approval.required ? `${approval.level} approval required` : "No approval required" },
        { id: generateId("event"), timestamp: new Date().toISOString(), actor: "EscalationEngine", action: "escalation_evaluation", details: escalation.required ? `Escalated to ${escalation.targetLevel}: ${escalation.reason}` : "No escalation required" },
        { id: generateId("event"), timestamp: new Date().toISOString(), actor: "RoutingEngine", action: "routing", details: `Routed to ${route.target}: ${route.reason}` },
      )

      outcomes.push({
        id: generateId("outcome"),
        sourceDecisionId: decision.id,
        sourceCategory: decision.category,
        state,
        route,
        approval,
        escalation,
        actions: generateActions(),
        policies,
        summary: `Decision "${decision.targetLabel}" → ${state} → ${route.target}. ${approval.required ? `${approval.level} approval required.` : "No approval required."} ${escalation.required ? `Escalated to ${escalation.targetLevel}.` : "No escalation."}`,
        timestamp: new Date().toISOString(),
      })
    }

    const audit = await DecisionAuditBuilder.buildAudit(generateId("decisions"), allEvents)

    const stateCounts: Record<DecisionState, number> = {
      draft: 0, pending_approval: 0, approved: 0, rejected: 0,
      needs_review: 0, escalated: 0, deferred: 0, revising: 0,
    }
    for (const o of outcomes) {
      stateCounts[o.state] = (stateCounts[o.state] || 0) + 1
    }

    const approvedCount = stateCounts["approved"]
    const reviewCount = stateCounts["needs_review"] + stateCounts["pending_approval"]
    const actionRequired = stateCounts["rejected"] + stateCounts["escalated"]

    return {
      outcomes,
      summary: `${outcomes.length} decisions evaluated. ${approvedCount} approved for execution, ${reviewCount} require review, ${actionRequired} require action.`,
      stateCounts,
      audit,
      timestamp: new Date().toISOString(),
    }
  },
}
