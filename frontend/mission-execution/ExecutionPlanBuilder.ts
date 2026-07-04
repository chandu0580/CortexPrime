import type { ExecutionPlan, DistributionStrategy, AssignmentPolicy } from "./types"
import { MissionDecompositionEngine } from "./MissionDecompositionEngine"

const VALIDATION_RULES = [
  { field: "totalTasks", operator: "gte" as const, value: 1, message: "Plan must have at least one task" },
  { field: "maxConcurrency", operator: "gte" as const, value: 1, message: "Max concurrency must be at least 1" },
  { field: "phases", operator: "exists" as const, value: null, message: "Plan must have phases" },
]

export const ExecutionPlanBuilder = {
  async createPlan(
    sessionId: string,
    missionId: string,
    strategy: DistributionStrategy = "balanced",
    assignmentPolicy: AssignmentPolicy = "single",
    maxConcurrency: number = 5,
  ): Promise<ExecutionPlan> {
    const plan = await MissionDecompositionEngine.decomposeMission(sessionId, missionId)
    plan.distributionStrategy = strategy
    plan.assignmentPolicy = assignmentPolicy
    plan.maxConcurrency = maxConcurrency
    return plan
  },

  async validatePlan(planId: string): Promise<{ valid: boolean; errors: string[] }> {
    const plan = await MissionDecompositionEngine.getPlan(planId)
    if (!plan) return { valid: false, errors: ["Plan not found"] }

    const errors: string[] = []
    for (const rule of VALIDATION_RULES) {
      const value = (plan as unknown as Record<string, unknown>)[rule.field]
      if (rule.operator === "gte") {
        const numVal = typeof value === "number" ? value : 0
        const threshold = typeof rule.value === "number" ? rule.value : 0
        if (numVal < threshold) errors.push(rule.message)
      }
      if (rule.operator === "exists" && (value === undefined || value === null)) {
        errors.push(rule.message)
      }
    }

    if (plan.phases.length === 0) errors.push("Plan has no phases")
    if (plan.totalTasks === 0) errors.push("Plan has no tasks")

    return { valid: errors.length === 0, errors }
  },

  async optimizePlan(planId: string): Promise<ExecutionPlan> {
    const plan = await MissionDecompositionEngine.getPlan(planId)
    if (!plan) throw new Error(`Plan ${planId} not found`)

    const totalWork = plan.totalTasks
    let optimalConcurrency = 5

    if (totalWork <= 5) optimalConcurrency = 2
    else if (totalWork <= 20) optimalConcurrency = 5
    else if (totalWork <= 50) optimalConcurrency = 10
    else optimalConcurrency = 20

    if (plan.distributionStrategy === "sequential") optimalConcurrency = 1

    plan.maxConcurrency = Math.min(plan.maxConcurrency, optimalConcurrency)
    plan.updatedAt = new Date().toISOString()
    return plan
  },

  async finalizePlan(planId: string): Promise<ExecutionPlan> {
    const plan = await MissionDecompositionEngine.getPlan(planId)
    if (!plan) throw new Error(`Plan ${planId} not found`)

    const validation = await this.validatePlan(planId)
    if (!validation.valid) {
      throw new Error(`Cannot finalize plan with validation errors: ${validation.errors.join("; ")}`)
    }

    plan.finalized = true
    plan.validated = true
    plan.updatedAt = new Date().toISOString()
    return plan
  },
}
