import type { ValidationResult, CoordinationStage, CoordinationTask, WorkerDelegation, SynchronizationBarrier, CoordinationPlan } from "./types"
import { generateId } from "./shared"

const validations = new Map<string, ValidationResult>()

export const CoordinationValidationEngine = {
  async validateExecutionOrdering(stages: CoordinationStage[]): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    const sequences = stages.map((s) => s.sequence)
    for (let i = 0; i < sequences.length; i++) {
      if (sequences[i] !== i + 1) {
        errors.push(`Stage sequence gap at index ${i}: expected ${i + 1}, got ${sequences[i]}`)
      }
    }

    for (const stage of stages) {
      for (const task of stage.tasks) {
        for (const depId of task.dependencies) {
          const depExists = stages.some((s) => s.tasks.some((t) => t.id === depId))
          if (!depExists) {
            errors.push(`Task "${task.name}" depends on missing task: ${depId}`)
          }
        }
      }
    }

    if (stages.length === 0) warnings.push("No stages to validate")

    const result: ValidationResult = {
      id: generateId("cval"),
      type: "execution_ordering",
      passed: errors.length === 0,
      errors,
      warnings,
      details: { stageCount: stages.length },
    }
    validations.set(result.id, result)
    return result
  },

  async validateWorkerAssignments(tasks: CoordinationTask[], delegations: WorkerDelegation[]): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    const activeDelegations = delegations.filter((d) => d.status === "active")
    const delegatedTaskIds = new Set(activeDelegations.map((d) => d.taskId))

    for (const task of tasks) {
      if (task.workerId && !delegatedTaskIds.has(task.id)) {
        warnings.push(`Task "${task.name}" has worker assigned but no active delegation`)
      }
    }

    for (const del of activeDelegations) {
      const taskExists = tasks.some((t) => t.id === del.taskId)
      if (!taskExists) {
        errors.push(`Delegation ${del.id} references non-existent task: ${del.taskId}`)
      }
    }

    const result: ValidationResult = {
      id: generateId("cval"),
      type: "worker_assignments",
      passed: errors.length === 0,
      errors,
      warnings,
      details: { taskCount: tasks.length, delegationCount: delegations.length },
    }
    validations.set(result.id, result)
    return result
  },

  async validateDependencySatisfaction(tasks: CoordinationTask[]): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    const taskMap = new Map(tasks.map((t) => [t.id, t]))

    for (const task of tasks) {
      for (const depId of task.dependencies) {
        const dep = taskMap.get(depId)
        if (!dep) {
          errors.push(`Task "${task.name}" depends on missing task: ${depId}`)
        } else if (dep.state !== "completed") {
          warnings.push(`Task "${task.name}" depends on uncompleted task: "${dep.name}" (${dep.state})`)
        }
      }
    }

    const result: ValidationResult = {
      id: generateId("cval"),
      type: "dependency_satisfaction",
      passed: errors.length === 0,
      errors,
      warnings,
      details: { taskCount: tasks.length, dependencyCount: tasks.reduce((s, t) => s + t.dependencies.length, 0) },
    }
    validations.set(result.id, result)
    return result
  },

  async validateSynchronizationIntegrity(barriers: SynchronizationBarrier[]): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    for (const barrier of barriers) {
      if (barrier.requiredWorkers.length === 0) {
        errors.push(`Barrier "${barrier.name}" has no required workers`)
      }
      const missing = barrier.requiredWorkers.filter((w) => !barrier.arrivedWorkers.includes(w))
      if (barrier.state === "released" && missing.length > 0) {
        errors.push(`Barrier "${barrier.name}" released but workers have not arrived: ${missing.join(", ")}`)
      }
    }

    if (barriers.length === 0) warnings.push("No barriers to validate")

    const result: ValidationResult = {
      id: generateId("cval"),
      type: "sync_integrity",
      passed: errors.length === 0,
      errors,
      warnings,
      details: { barrierCount: barriers.length },
    }
    validations.set(result.id, result)
    return result
  },

  async validateCoordinationCompleteness(plans: CoordinationPlan[]): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    for (const plan of plans) {
      if (plan.stages.length === 0) warnings.push(`Plan "${plan.name}" has no stages`)
      if (plan.totalTasks === 0) warnings.push(`Plan "${plan.name}" has no tasks`)
      if (plan.completedTasks > plan.totalTasks) {
        errors.push(`Plan "${plan.name}" reports ${plan.completedTasks} completed but only ${plan.totalTasks} total`)
      }
    }

    if (plans.length === 0) warnings.push("No plans to validate")

    const result: ValidationResult = {
      id: generateId("cval"),
      type: "coordination_completeness",
      passed: errors.length === 0,
      errors,
      warnings,
      details: { planCount: plans.length },
    }
    validations.set(result.id, result)
    return result
  },

  async getValidations(type?: string): Promise<ValidationResult[]> {
    let result = Array.from(validations.values())
    if (type) result = result.filter((v) => v.type === type)
    return result
  },
}
