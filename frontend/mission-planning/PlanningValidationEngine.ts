import type { PlanningCheckpoint, PlanningValidationResult } from "./types"
import { MissionPlanner } from "./MissionPlanner"
import { DependencyPlanner } from "./DependencyPlanner"
import { ResourcePlanner } from "./ResourcePlanner"
import { PlanningPolicyEngine } from "./PlanningPolicyEngine"
import { generateId } from "@/worker-framework/shared"

export const PlanningValidationEngine = {
  async validateCompleteness(sessionId: string, planId: string): Promise<PlanningCheckpoint> {
    const plan = await MissionPlanner.getPlan(planId)
    const deps = await DependencyPlanner.getDependenciesBySession(sessionId)
    const resources = await ResourcePlanner.getResourcesBySession(sessionId)
    const policyResult = await PlanningPolicyEngine.evaluatePlanning(sessionId, "validate", { planId })

    const planComplete = plan !== null && plan.phases.length > 0 && plan.totalTasks > 0
    const dependenciesResolved = deps.length === 0 || deps.every((d) => d.resolved)
    const resourcesAvailable = resources.length === 0 || resources.every((r) => r.availableCount >= r.requiredCount)
    const timelineValid = plan !== null && plan.estimatedDurationMs > 0
    const priorityDefined = plan !== null && plan.priority !== undefined
    const policiesSatisfied = policyResult.allowed

    const ready = planComplete && dependenciesResolved && resourcesAvailable && timelineValid && priorityDefined && policiesSatisfied

    const checkpoint: PlanningCheckpoint = {
      id: generateId("plan-checkpoint"),
      sessionId,
      stage: "validation",
      dependenciesResolved,
      resourcesAvailable,
      timelineValid,
      priorityDefined,
      planComplete,
      ready,
      checkedAt: new Date().toISOString(),
    }
    return checkpoint
  },

  async validateAll(sessionId: string, planId: string): Promise<{ result: PlanningValidationResult; reasons: string[] }> {
    const checkpoint = await this.validateCompleteness(sessionId, planId)
    const reasons: string[] = []

    if (!checkpoint.planComplete) reasons.push("Plan incomplete")
    if (!checkpoint.dependenciesResolved) reasons.push("Dependencies not resolved")
    if (!checkpoint.resourcesAvailable) reasons.push("Resources not available")
    if (!checkpoint.timelineValid) reasons.push("Timeline invalid")
    if (!checkpoint.priorityDefined) reasons.push("Priority not defined")

    if (checkpoint.ready) return { result: "pass", reasons }
    if (reasons.length <= 2) return { result: "warning", reasons }
    return { result: "fail", reasons }
  },
}
