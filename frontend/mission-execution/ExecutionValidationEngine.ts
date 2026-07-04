import type { ExecutionCheckpoint, ExecutionStage, ValidationResult } from "./types"
import { ExecutionDependencyManager } from "./ExecutionDependencyManager"
import { ExecutionPlanBuilder } from "./ExecutionPlanBuilder"
import { TaskDistributionEngine } from "./TaskDistributionEngine"
import { ExecutionPolicyEngine } from "./ExecutionPolicyEngine"
import { generateId } from "@/worker-framework/shared"

export const ExecutionValidationEngine = {
  async validateReadiness(sessionId: string, planId: string, stage: ExecutionStage): Promise<ExecutionCheckpoint> {
    const depValidation = await ExecutionDependencyManager.validateDependencies(sessionId)
    const planValidation = planId ? await ExecutionPlanBuilder.validatePlan(planId) : { valid: false, errors: ["No plan"] }
    const assignments = await TaskDistributionEngine.getAssignmentsBySession(sessionId)
    const policyResult = await ExecutionPolicyEngine.evaluateExecution(sessionId, "validate", {})

    const dependenciesResolved = depValidation.valid
    const planValidated = planValidation.valid
    const assignmentsComplete = assignments.length > 0
    const policiesSatisfied = policyResult.allowed

    const ready = dependenciesResolved && planValidated && assignmentsComplete && policiesSatisfied

    const checkpoint: ExecutionCheckpoint = {
      id: generateId("exec-checkpoint"),
      sessionId,
      stage,
      planId,
      dependenciesResolved,
      assignmentsComplete,
      planValidated,
      policiesSatisfied,
      ready,
      checkedAt: new Date().toISOString(),
    }
    return checkpoint
  },

  async validateAll(sessionId: string, planId: string): Promise<{ result: ValidationResult; reasons: string[] }> {
    const checkpoint = await this.validateReadiness(sessionId, planId, "validation")
    const reasons: string[] = []

    if (!checkpoint.dependenciesResolved) reasons.push("Dependencies not resolved")
    if (!checkpoint.planValidated) reasons.push("Plan not validated")
    if (!checkpoint.assignmentsComplete) reasons.push("Assignments not complete")
    if (!checkpoint.policiesSatisfied) reasons.push("Policies not satisfied")

    if (checkpoint.ready) return { result: "pass", reasons }
    if (reasons.length <= 2) return { result: "warning", reasons }
    return { result: "fail", reasons }
  },

  async validateStage(stage: ExecutionStage, sessionId: string): Promise<ValidationResult> {
    const session = await import("./ExecutionSessionManager").then((m) => m.ExecutionSessionManager.getSession(sessionId))
    if (!session) return "fail"

    switch (stage) {
      case "decomposition":
        return session.planId ? "pass" : "fail"
      case "planning":
        return session.planId ? (await ExecutionPlanBuilder.validatePlan(session.planId)).valid ? "pass" : "fail" : "fail"
      case "distribution":
        return "pass"
      case "dependency_check":
        return (await ExecutionDependencyManager.validateDependencies(sessionId)).valid ? "pass" : "fail"
      case "validation": {
        if (!session.planId) return "fail"
        return (await this.validateAll(sessionId, session.planId)).result
      }
      case "execution":
        return "pass"
      case "monitoring":
        return "pass"
      case "completion":
        return "pass"
      default:
        return "skip"
    }
  },
}
