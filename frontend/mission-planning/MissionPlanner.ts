import type { MissionPlan, PlanningPhase, PlanningTask, PlanningStrategy, PlanningPriority, PlanningState } from "./types"
import { generateId } from "@/worker-framework/shared"

const plans = new Map<string, MissionPlan>()

export const MissionPlanner = {
  async createMissionPlan(
    sessionId: string,
    missionId: string,
    name: string,
    description: string,
    strategy: PlanningStrategy = "iterative",
    priority: PlanningPriority = "medium",
  ): Promise<MissionPlan> {
    const now = new Date().toISOString()
    const plan: MissionPlan = {
      id: generateId("mission-plan"),
      sessionId,
      missionId,
      name,
      description,
      phases: [],
      priority,
      strategy,
      estimatedDurationMs: 0,
      totalTasks: 0,
      validated: false,
      finalized: false,
      createdAt: now,
      updatedAt: now,
    }
    plans.set(plan.id, plan)
    return plan
  },

  async getPlan(planId: string): Promise<MissionPlan | null> {
    return plans.get(planId) ?? null
  },

  async updatePlan(planId: string, updates: Partial<MissionPlan>): Promise<MissionPlan> {
    const plan = plans.get(planId)
    if (!plan) throw new Error(`MissionPlan ${planId} not found`)
    const updated: MissionPlan = { ...plan, ...updates, updatedAt: new Date().toISOString() }
    plans.set(planId, updated)
    return updated
  },

  async decomposeMission(planId: string, phases: Omit<PlanningPhase, "id">[]): Promise<MissionPlan> {
    const plan = await this.getPlan(planId)
    if (!plan) throw new Error(`MissionPlan ${planId} not found`)

    const now = new Date().toISOString()
    const builtPhases: PlanningPhase[] = phases.map((p, i) => ({
      id: generateId("plan-phase"),
      ...p,
      order: i + 1,
      status: p.status ?? "draft",
      startedAt: p.startedAt ?? null,
      completedAt: p.completedAt ?? null,
    }))

    const totalTasks = builtPhases.reduce((sum, p) => sum + p.tasks.length, 0)
    const estimatedDurationMs = builtPhases.reduce((sum, p) => sum + p.estimatedDurationMs, 0)

    plan.phases = builtPhases
    plan.totalTasks = totalTasks
    plan.estimatedDurationMs = estimatedDurationMs
    plan.updatedAt = now
    return plan
  },

  async buildPlanningPhases(planId: string, taskData: { name: string; description: string; workerType: string; capabilities: string[]; effortMs: number }[][]): Promise<MissionPlan> {
    const plan = await this.getPlan(planId)
    if (!plan) throw new Error(`MissionPlan ${planId} not found`)

    const now = new Date().toISOString()
    const phases: PlanningPhase[] = taskData.map((phaseTasks, pi) => {
      const tasks: PlanningTask[] = phaseTasks.map((t, ti) => ({
        id: generateId("plan-task"),
        phaseId: "",
        name: t.name,
        description: t.description,
        workerType: t.workerType,
        requiredCapabilities: t.capabilities,
        priority: ti + 1,
        estimatedEffortMs: t.effortMs,
        dependencies: [],
        status: "draft" as PlanningState,
        assignedWorkerId: null,
        createdAt: now,
      }))

      const phase: PlanningPhase = {
        id: generateId("plan-phase"),
        name: `Phase ${pi + 1}`,
        order: pi + 1,
        description: `Planning phase ${pi + 1}`,
        tasks,
        status: "draft" as PlanningState,
        startedAt: null,
        completedAt: null,
        estimatedDurationMs: tasks.reduce((sum, t) => sum + t.estimatedEffortMs, 0),
      }

      tasks.forEach((t) => { t.phaseId = phase.id })
      return phase
    })

    const totalTasks = phases.reduce((sum, p) => sum + p.tasks.length, 0)
    const estimatedDurationMs = phases.reduce((sum, p) => sum + p.estimatedDurationMs, 0)

    plan.phases = phases
    plan.totalTasks = totalTasks
    plan.estimatedDurationMs = estimatedDurationMs
    plan.updatedAt = now
    return plan
  },

  async generateExecutionSequence(planId: string): Promise<MissionPlan> {
    const plan = await this.getPlan(planId)
    if (!plan) throw new Error(`MissionPlan ${planId} not found`)

    plan.phases.sort((a, b) => a.order - b.order)
    for (const phase of plan.phases) {
      phase.tasks.sort((a, b) => a.priority - b.priority)
    }
    plan.updatedAt = new Date().toISOString()
    return plan
  },

  async finalizePlan(planId: string): Promise<MissionPlan> {
    const plan = await this.getPlan(planId)
    if (!plan) throw new Error(`MissionPlan ${planId} not found`)

    plan.finalized = true
    plan.validated = true
    plan.updatedAt = new Date().toISOString()
    return plan
  },

  async getPlansBySession(sessionId: string): Promise<MissionPlan[]> {
    return Array.from(plans.values()).filter((p) => p.sessionId === sessionId)
  },

  async getAllPlans(): Promise<MissionPlan[]> {
    return Array.from(plans.values())
  },
}
