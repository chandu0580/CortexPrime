import type { GovernanceSession, GovernancePolicy, PolicyEvaluation, ComplianceResult, ApprovalRequest, ApprovalDecision, RiskAssessment, GovernanceDecision, GovernanceCheckpoint, GovernanceAudit, GovernanceMetrics, GovernanceHealth, GovernanceCapabilityDefinition, ValidationResult, HealthSnapshot } from "./types"
import type { PolicyResult, ComplianceState, ApprovalState, RiskLevel } from "./types"
import { GovernanceSessionManager } from "./GovernanceSessionManager"
import { PolicyRegistry } from "./PolicyRegistry"
import { PolicyEvaluationEngine } from "./PolicyEvaluationEngine"
import { ComplianceEngine } from "./ComplianceEngine"
import { ApprovalEngine } from "./ApprovalEngine"
import { RiskControlEngine } from "./RiskControlEngine"
import { GovernanceDecisionEngine } from "./GovernanceDecisionEngine"
import { GovernanceAuditManager } from "./GovernanceAuditManager"
import { GovernanceValidationEngine } from "./GovernanceValidationEngine"
import { GovernanceMetricsCollector } from "./GovernanceMetricsCollector"
import { GovernanceHealthManager } from "./GovernanceHealthManager"
import { GovernanceCapability } from "./GovernanceCapability"
import { cortexEventBus } from "@/event-bus/cortexEventBus"

export const GovernanceEngine = {
  async evaluate(sessionId: string, data: Record<string, unknown>): Promise<{ evaluations: PolicyEvaluation[]; decision: GovernanceDecision; session: GovernanceSession }> {
    const session = await GovernanceSessionManager.getSession(sessionId)
    if (!session) throw new Error(`Governance session not found: ${sessionId}`)

    const policies = await PolicyRegistry.listPolicies()
    const enabledPolicies = policies.filter((p) => p.enabled && session.policyIds.includes(p.id))

    const evaluations = await PolicyEvaluationEngine.evaluatePolicies(enabledPolicies, sessionId, data)

    const failedEvaluations = evaluations.filter((e) => e.result === "fail")
    const hasFailures = failedEvaluations.length > 0

    const decision = await GovernanceDecisionEngine.decide(
      sessionId,
      "evaluate",
      hasFailures ? "deny" : "allow",
      hasFailures ? `${failedEvaluations.length} policy evaluations failed` : "All policy evaluations passed",
      "GovernanceEngine",
    )

    if (hasFailures) {
      await GovernanceHealthManager.recordFailedEvaluation()
    }

    await cortexEventBus.publish("governance", "governance", `governance.evaluate.${decision.result}`, "GovernanceEngine", {
      sessionId,
      evaluationCount: evaluations.length,
      decisionId: decision.id,
      result: decision.result,
    }, hasFailures ? "high" : "low", sessionId)

    return { evaluations, decision, session }
  },

  async validate(type: string, data: Record<string, unknown>): Promise<ValidationResult> {
    let result: ValidationResult

    switch (type) {
      case "policy_integrity": {
        const policy = data as unknown as GovernancePolicy
        result = await GovernanceValidationEngine.validatePolicyIntegrity(policy)
        break
      }
      case "compliance_consistency": {
        const results = data as unknown as ComplianceResult[]
        result = await GovernanceValidationEngine.validateComplianceConsistency(results)
        break
      }
      case "approval_chain": {
        const requests = data as unknown as ApprovalRequest[]
        result = await GovernanceValidationEngine.validateApprovalChain(requests)
        break
      }
      case "governance_rules": {
        const policies = data as unknown as GovernancePolicy[]
        result = await GovernanceValidationEngine.validateGovernanceRules(policies)
        break
      }
      case "audit_completeness": {
        const records = data as unknown as GovernanceAudit[]
        result = await GovernanceValidationEngine.validateAuditCompleteness(records)
        break
      }
      default:
        throw new Error(`Unknown validation type: ${type}`)
    }

    await cortexEventBus.publish("governance", "governance", `governance.validate.${type}`, "GovernanceEngine", {
      validationId: result.id,
      passed: result.passed,
      errors: result.errors.length,
    }, result.passed ? "low" : "high", "governance")

    return result
  },

  async approve(sessionId: string, action: string, requestedBy: string, reason: string): Promise<{ request: ApprovalRequest }> {
    const request = await ApprovalEngine.requestApproval(sessionId, action, requestedBy, reason)

    await cortexEventBus.publish("governance", "governance", "governance.approval.requested", "GovernanceEngine", {
      requestId: request.id,
      sessionId,
      action,
      requestedBy,
    }, "normal", sessionId)

    return { request }
  },

  async approveRequest(requestId: string, approver: string, reason: string): Promise<{ request: ApprovalRequest; decision: ApprovalDecision }> {
    const result = await ApprovalEngine.approve(requestId, approver, reason)

    await cortexEventBus.publish("governance", "governance", "governance.approval.approved", "GovernanceEngine", {
      requestId,
      approver,
      reason,
    }, "low", result.request.sessionId)

    return result
  },

  async rejectRequest(requestId: string, approver: string, reason: string): Promise<{ request: ApprovalRequest; decision: ApprovalDecision }> {
    const result = await ApprovalEngine.reject(requestId, approver, reason)

    await GovernanceHealthManager.recordApprovalFailure()
    await cortexEventBus.publish("governance", "governance", "governance.approval.rejected", "GovernanceEngine", {
      requestId,
      approver,
      reason,
    }, "high", result.request.sessionId)

    return result
  },

  async audit(sessionId: string, action: string, actor: string, target: string, detail: string, metadata?: Record<string, unknown>): Promise<GovernanceAudit> {
    const record = await GovernanceAuditManager.recordAudit(sessionId, action, actor, target, detail, metadata)

    await cortexEventBus.publish("governance", "governance", `governance.audit.${action}`, "GovernanceEngine", {
      auditId: record.id,
      sessionId,
      action,
      actor,
      target,
    }, "low", sessionId)

    return record
  },

  async assessRisk(sessionId: string, factors: string[], details?: Record<string, unknown>): Promise<RiskAssessment> {
    const assessment = await RiskControlEngine.assessRisk(sessionId, factors, details)

    if (assessment.level === "critical" || assessment.level === "high") {
      await cortexEventBus.publish("governance", "governance", "governance.risk.alert", "GovernanceEngine", {
        assessmentId: assessment.id,
        sessionId,
        level: assessment.level,
        score: assessment.score,
        factors: assessment.factors,
      }, "high", sessionId)
    }

    return assessment
  },

  async metrics(): Promise<GovernanceMetrics> {
    return GovernanceMetricsCollector.collectAll()
  },

  async health(): Promise<GovernanceHealth> {
    return GovernanceHealthManager.getHealth()
  },

  async createSession(missionId: string, policyIds?: string[], metadata?: Record<string, unknown>): Promise<GovernanceSession> {
    const session = await GovernanceSessionManager.createSession(missionId, policyIds, metadata)

    await cortexEventBus.publish("governance", "governance", "governance.session.created", "GovernanceEngine", {
      sessionId: session.id,
      missionId,
      policyCount: policyIds?.length ?? 0,
    }, "low", session.id)

    return session
  },

  async closeSession(sessionId: string): Promise<GovernanceSession> {
    const session = await GovernanceSessionManager.closeSession(sessionId)

    await GovernanceAuditManager.recordAudit(sessionId, "session.closed", "GovernanceEngine", sessionId, "Governance session closed")

    await cortexEventBus.publish("governance", "governance", "governance.session.closed", "GovernanceEngine", {
      sessionId,
    }, "low", sessionId)

    return session
  },

  async registerPolicy(name: string, description: string, category: string, rules: import("./types").PolicyRule[], version?: string, priority?: number, tags?: Record<string, string>): Promise<GovernancePolicy> {
    const policy = await PolicyRegistry.registerPolicy(name, description, category, rules, version, priority, tags)

    await cortexEventBus.publish("governance", "governance", "governance.policy.registered", "GovernanceEngine", {
      policyId: policy.id,
      name,
      category,
      ruleCount: rules.length,
    }, "low", "governance")

    return policy
  },

  async addCheckpoint(sessionId: string, stage: string, status: "pending" | "passed" | "failed" | "skipped", details?: string): Promise<GovernanceCheckpoint> {
    return GovernanceSessionManager.addCheckpoint(sessionId, stage, status, details)
  },

  async getCapabilities(): Promise<GovernanceCapabilityDefinition[]> {
    return GovernanceCapability.list()
  },

  async isCapabilityEnabled(name: string): Promise<boolean> {
    return GovernanceCapability.isEnabled(name)
  },

  async snapshot(component: string, metrics: Record<string, number>, details?: string): Promise<HealthSnapshot> {
    return GovernanceHealthManager.snapshot(component, metrics, details)
  },

  async timeline(sessionId: string): Promise<GovernanceAudit[]> {
    return GovernanceAuditManager.buildTimeline(sessionId)
  },
}
