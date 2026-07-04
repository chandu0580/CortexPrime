import type { OrchestrationReport } from "@/mission-orchestrator/types"
import type { EnterpriseDecisionResult } from "@/enterprise-decision/types"
import type { ExecutionReadinessReport } from "./types"
import { DependencyValidationEngine } from "./DependencyValidationEngine"
import { CapabilityValidationEngine } from "./CapabilityValidationEngine"
import { PolicyValidationEngine } from "./PolicyValidationEngine"
import { AuthorizationEngine } from "./AuthorizationEngine"
import { ReadinessAssessmentEngine } from "./ReadinessAssessmentEngine"
import { generateId } from "./shared"

export const executionReadinessEngine = {
  async generateReadinessReport(
    report: OrchestrationReport,
    decisionResult: EnterpriseDecisionResult,
  ): Promise<ExecutionReadinessReport> {
    const { dependencyChecks, dependencies } = await DependencyValidationEngine.validateDependencies(report.graph)
    const { capabilityChecks, prerequisites } = await CapabilityValidationEngine.validateCapabilities(report.graph, report.assignments)
    const { policyChecks, policies } = await PolicyValidationEngine.validatePolicies(decisionResult)
    const { authorization, approval, authorizationChecks } = await AuthorizationEngine.evaluateAuthorization(decisionResult)

    const allChecks = [...dependencyChecks, ...capabilityChecks, ...policyChecks, ...authorizationChecks]

    const { overallStatus, blockers, window, passingChecks, totalChecks, summary } =
      await ReadinessAssessmentEngine.assessReadiness(report.graph, allChecks)

    return {
      id: generateId("readiness"),
      overallStatus,
      checks: allChecks,
      policies,
      approval,
      blockers,
      dependencies,
      authorization,
      window,
      prerequisites,
      passingChecks,
      totalChecks,
      summary,
      timestamp: new Date().toISOString(),
    }
  },
}
