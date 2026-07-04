import type { GovernanceMetrics } from "./types"
import { PolicyEvaluationEngine } from "./PolicyEvaluationEngine"
import { ApprovalEngine } from "./ApprovalEngine"
import { ComplianceEngine } from "./ComplianceEngine"
import { RiskControlEngine } from "./RiskControlEngine"
import { GovernanceDecisionEngine } from "./GovernanceDecisionEngine"
import { GovernanceSessionManager } from "./GovernanceSessionManager"

export const GovernanceMetricsCollector = {
  async collectAll(): Promise<GovernanceMetrics> {
    const sessions = await GovernanceSessionManager.listSessions()
    const evaluations = await PolicyEvaluationEngine.getEvaluationCount()
    const approvals = await ApprovalEngine.requestCount()
    const violations = await ComplianceEngine.getViolationCount()
    const decisions = await GovernanceDecisionEngine.decisionCount()
    const riskAssessments = await RiskControlEngine.assessmentCount()

    return {
      totalSessions: sessions.length,
      activeSessions: sessions.filter((s) => s.state === "active").length,
      totalEvaluations: evaluations,
      totalApprovals: approvals,
      totalViolations: violations,
      totalDecisions: decisions,
      totalComplianceChecks: evaluations,
      totalRiskAssessments: riskAssessments,
    }
  },

  async collectSessions(): Promise<{ total: number; active: number }> {
    const sessions = await GovernanceSessionManager.listSessions()
    return {
      total: sessions.length,
      active: sessions.filter((s) => s.state === "active").length,
    }
  },

  async collectEvaluations(): Promise<number> {
    return PolicyEvaluationEngine.getEvaluationCount()
  },

  async collectApprovals(): Promise<number> {
    return ApprovalEngine.requestCount()
  },

  async collectViolations(): Promise<number> {
    return ComplianceEngine.getViolationCount()
  },

  async collectDecisions(): Promise<number> {
    return GovernanceDecisionEngine.decisionCount()
  },

  async collectRiskAssessments(): Promise<number> {
    return RiskControlEngine.assessmentCount()
  },
}
