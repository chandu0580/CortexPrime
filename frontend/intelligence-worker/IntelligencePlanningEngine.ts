import type { IntelligencePlan, IntelligenceStage, IntelligenceObjective } from "./types"
import { generateId } from "@/worker-framework/shared"

const plans = new Map<string, IntelligencePlan>()

export const IntelligencePlanningEngine = {
  async createPlan(sessionId: string): Promise<IntelligencePlan> {
    const plan: IntelligencePlan = {
      id: generateId("intel-plan"),
      sessionId,
      status: "draft",
      objectives: [],
      stages: [],
      progress: 0,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      completedAt: null,
    }
    plans.set(plan.id, plan)
    return plan
  },

  async getPlan(planId: string): Promise<IntelligencePlan | null> {
    return plans.get(planId) ?? null
  },

  async addObjective(planId: string, description: string, key: string, target: string): Promise<IntelligenceObjective> {
    const plan = plans.get(planId)
    if (!plan) throw new Error(`Intelligence plan ${planId} not found`)

    const objective: IntelligenceObjective = {
      id: generateId("intel-objective"),
      planId,
      description,
      key,
      target,
      completed: false,
      completedAt: null,
    }
    plan.objectives.push(objective)
    plan.updatedAt = new Date().toISOString()
    return objective
  },

  async addStage(planId: string, name: string, description: string, order: number): Promise<IntelligenceStage> {
    const plan = plans.get(planId)
    if (!plan) throw new Error(`Intelligence plan ${planId} not found`)

    const stage: IntelligenceStage = {
      id: generateId("intel-stage"),
      planId,
      name,
      description,
      order,
      status: "pending",
      startedAt: null,
      completedAt: null,
      durationMs: null,
    }
    plan.stages.push(stage)
    plan.stages.sort((a, b) => a.order - b.order)
    plan.updatedAt = new Date().toISOString()
    return stage
  },

  async reorderStages(planId: string, stageIds: string[]): Promise<void> {
    const plan = plans.get(planId)
    if (!plan) throw new Error(`Intelligence plan ${planId} not found`)

    const stageMap = new Map(plan.stages.map((s) => [s.id, s]))
    const reordered: IntelligenceStage[] = []

    for (let i = 0; i < stageIds.length; i++) {
      const stage = stageMap.get(stageIds[i])
      if (!stage) throw new Error(`Stage ${stageIds[i]} not found in plan ${planId}`)
      reordered.push({ ...stage, order: i + 1 })
    }

    plan.stages = reordered
    plan.updatedAt = new Date().toISOString()
  },

  async startStage(planId: string, stageId: string): Promise<void> {
    const plan = plans.get(planId)
    if (!plan) throw new Error(`Intelligence plan ${planId} not found`)
    const stage = plan.stages.find((s) => s.id === stageId)
    if (!stage) throw new Error(`Stage ${stageId} not found in plan ${planId}`)
    stage.status = "in_progress"
    stage.startedAt = new Date().toISOString()
    plan.updatedAt = new Date().toISOString()
  },

  async completeStage(planId: string, stageId: string): Promise<void> {
    const plan = plans.get(planId)
    if (!plan) throw new Error(`Intelligence plan ${planId} not found`)
    const stage = plan.stages.find((s) => s.id === stageId)
    if (!stage) throw new Error(`Stage ${stageId} not found in plan ${planId}`)
    const now = new Date().toISOString()
    const start = stage.startedAt ? new Date(stage.startedAt).getTime() : Date.now()
    stage.status = "completed"
    stage.completedAt = now
    stage.durationMs = Date.now() - start
    plan.updatedAt = new Date().toISOString()
  },

  async failStage(planId: string, stageId: string): Promise<void> {
    const plan = plans.get(planId)
    if (!plan) throw new Error(`Intelligence plan ${planId} not found`)
    const stage = plan.stages.find((s) => s.id === stageId)
    if (!stage) throw new Error(`Stage ${stageId} not found in plan ${planId}`)
    stage.status = "failed"
    stage.completedAt = new Date().toISOString()
    plan.updatedAt = new Date().toISOString()
  },

  async calculateProgress(planId: string): Promise<number> {
    const plan = plans.get(planId)
    if (!plan) return 0

    const totalStages = plan.stages.length
    if (totalStages === 0) return 0

    const completedStages = plan.stages.filter((s) => s.status === "completed").length
    const inProgressStages = plan.stages.filter((s) => s.status === "in_progress").length

    const progress = Math.round(((completedStages + inProgressStages * 0.5) / totalStages) * 100)
    plan.progress = progress
    return progress
  },

  async activatePlan(planId: string): Promise<void> {
    const plan = plans.get(planId)
    if (!plan) throw new Error(`Intelligence plan ${planId} not found`)
    if (plan.status !== "draft") throw new Error(`Cannot activate plan in status ${plan.status}`)
    plan.status = "active"
    plan.updatedAt = new Date().toISOString()
  },

  async completePlan(planId: string): Promise<void> {
    const plan = plans.get(planId)
    if (!plan) throw new Error(`Intelligence plan ${planId} not found`)
    plan.status = "completed"
    plan.progress = 100
    plan.completedAt = new Date().toISOString()
    plan.updatedAt = new Date().toISOString()
  },

  async markPlanFailed(planId: string): Promise<void> {
    const plan = plans.get(planId)
    if (!plan) throw new Error(`Intelligence plan ${planId} not found`)
    plan.status = "failed"
    plan.updatedAt = new Date().toISOString()
  },

  async getPlansBySession(sessionId: string): Promise<IntelligencePlan[]> {
    return Array.from(plans.values()).filter((p) => p.sessionId === sessionId)
  },

  async clearSession(sessionId: string): Promise<void> {
    for (const [id, plan] of plans.entries()) {
      if (plan.sessionId === sessionId) {
        plans.delete(id)
      }
    }
  },
}
