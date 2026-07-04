import type { CoordinationPlan, CoordinationStage, CoordinationTask, CoordinationStrategy, CoordinationState, CoordinationResult } from "./types"
import { generateId } from "./shared"

const plans = new Map<string, CoordinationPlan>()

export const CoordinationPlanner = {
  async createPlan(sessionId: string, name: string, strategy: CoordinationStrategy = "sequential"): Promise<CoordinationPlan> {
    const id = generateId("cplan")
    const plan: CoordinationPlan = {
      id,
      sessionId,
      name,
      stages: [],
      totalTasks: 0,
      completedTasks: 0,
      strategy,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }
    plans.set(id, plan)
    return plan
  },

  async buildStages(planId: string, stageNames: string[]): Promise<CoordinationStage[]> {
    const plan = plans.get(planId)
    if (!plan) throw new Error(`Coordination plan not found: ${planId}`)
    const stages: CoordinationStage[] = stageNames.map((name, index) => ({
      id: generateId("cstage"),
      name,
      sequence: index + 1,
      tasks: [],
      state: index === 0 ? "active" : "paused",
      startedAt: index === 0 ? new Date().toISOString() : null,
      completedAt: null,
    }))
    const updated: CoordinationPlan = { ...plan, stages, updatedAt: new Date().toISOString() }
    plans.set(planId, updated)
    return stages
  },

  async sequenceTasks(planId: string, stageIndex: number, taskNames: string[], dependencies: string[][] = []): Promise<CoordinationTask[]> {
    const plan = plans.get(planId)
    if (!plan) throw new Error(`Coordination plan not found: ${planId}`)
    if (stageIndex < 0 || stageIndex >= plan.stages.length) throw new Error(`Stage index ${stageIndex} out of range`)

    const tasks: CoordinationTask[] = taskNames.map((name, index) => ({
      id: generateId("ctask"),
      name,
      stageId: plan.stages[stageIndex].id,
      workerId: null,
      dependencies: dependencies[index] ?? [],
      state: "active",
      priority: 50,
      estimatedDuration: 0,
      startedAt: null,
      completedAt: null,
      result: null,
      metadata: {},
    }))

    const stages = [...plan.stages]
    stages[stageIndex] = { ...stages[stageIndex], tasks }
    const totalTasks = stages.reduce((sum, s) => sum + s.tasks.length, 0)
    const updated: CoordinationPlan = { ...plan, stages, totalTasks, updatedAt: new Date().toISOString() }
    plans.set(planId, updated)
    return tasks
  },

  async optimizeExecution(planId: string): Promise<CoordinationPlan> {
    const plan = plans.get(planId)
    if (!plan) throw new Error(`Coordination plan not found: ${planId}`)
    const stages = plan.stages.map((stage) => ({
      ...stage,
      tasks: [...stage.tasks].sort((a, b) => a.priority - b.priority),
    }))
    const updated: CoordinationPlan = { ...plan, stages, updatedAt: new Date().toISOString() }
    plans.set(planId, updated)
    return updated
  },

  async finalizePlan(planId: string): Promise<CoordinationPlan> {
    const plan = plans.get(planId)
    if (!plan) throw new Error(`Coordination plan not found: ${planId}`)
    if (plan.stages.length === 0) throw new Error("Cannot finalize plan with no stages")
    const totalTasks = plan.stages.reduce((sum, s) => sum + s.tasks.length, 0)
    const updated: CoordinationPlan = { ...plan, totalTasks, updatedAt: new Date().toISOString() }
    plans.set(planId, updated)
    return updated
  },

  async completeTask(planId: string, taskId: string, result: CoordinationResult): Promise<CoordinationTask> {
    const plan = plans.get(planId)
    if (!plan) throw new Error(`Coordination plan not found: ${planId}`)

    for (let i = 0; i < plan.stages.length; i++) {
      const taskIndex = plan.stages[i].tasks.findIndex((t) => t.id === taskId)
      if (taskIndex !== -1) {
        const stages = [...plan.stages]
        const task = stages[i].tasks[taskIndex]
        const updatedTask: CoordinationTask = {
          ...task,
          state: result === "failure" ? "failed" : "completed",
          completedAt: new Date().toISOString(),
          result,
        }
        const tasks = [...stages[i].tasks]
        tasks[taskIndex] = updatedTask
        stages[i] = { ...stages[i], tasks }
        const completedTasks = stages.reduce((sum, s) => sum + s.tasks.filter((t) => t.state === "completed" || t.state === "failed").length, 0)
        const allDone = stages[i].tasks.every((t) => t.state === "completed" || t.state === "failed")
        if (allDone && i + 1 < stages.length) {
          stages[i + 1] = { ...stages[i + 1], state: "active", startedAt: new Date().toISOString() }
        }
        const updated: CoordinationPlan = { ...plan, stages, completedTasks, updatedAt: new Date().toISOString() }
        plans.set(planId, updated)
        return updatedTask
      }
    }
    throw new Error(`Task not found: ${taskId}`)
  },

  async getPlan(planId: string): Promise<CoordinationPlan | null> {
    return plans.get(planId) ?? null
  },

  async listPlans(sessionId?: string): Promise<CoordinationPlan[]> {
    let result = Array.from(plans.values())
    if (sessionId) result = result.filter((p) => p.sessionId === sessionId)
    return result
  },
}
