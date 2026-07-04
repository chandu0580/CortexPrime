import type { ExecutionPlan, ExecutionPhase, ExecutionBatch, DistributedTask, ExecutionDependency, ExecutionStage, ExecutionState } from "./types"
import { generateId } from "@/worker-framework/shared"

const decompositionPlans = new Map<string, ExecutionPlan>()

const DEFAULT_STAGES: ExecutionStage[] = [
  "decomposition",
  "planning",
  "distribution",
  "dependency_check",
  "validation",
  "execution",
  "monitoring",
  "completion",
]

export const MissionDecompositionEngine = {
  async decomposeMission(
    sessionId: string,
    missionId: string,
    phases?: { name: string; tasks: { name: string; description: string; workerType: string; capabilities: string[]; priority: number }[] }[],
  ): Promise<ExecutionPlan> {
    const now = new Date().toISOString()
    const builtPhases: ExecutionPhase[] = (phases ?? this.defaultPhases()).map((p, pi) => ({
      id: generateId("exec-phase"),
      name: p.name,
      order: pi + 1,
      stages: DEFAULT_STAGES.map((s, si) => ({
        id: generateId("exec-stage"),
        name: s,
        order: si + 1,
        status: "pending" as ExecutionState,
        startedAt: null,
        completedAt: null,
        durationMs: null,
        error: null,
      })),
      status: "pending" as ExecutionState,
      startedAt: null,
      completedAt: null,
    }))

    const totalTasks = phases?.reduce((sum, p) => sum + p.tasks.length, 0) ?? 0

    const plan: ExecutionPlan = {
      id: generateId("exec-plan"),
      sessionId,
      phases: builtPhases,
      totalTasks,
      distributionStrategy: "balanced",
      assignmentPolicy: "single",
      maxConcurrency: 5,
      validated: false,
      finalized: false,
      createdAt: now,
      updatedAt: now,
    }
    decompositionPlans.set(plan.id, plan)
    return plan
  },

  async buildExecutionStages(planId: string, stages: ExecutionStage[]): Promise<ExecutionPlan> {
    const plan = decompositionPlans.get(planId)
    if (!plan) throw new Error(`Plan ${planId} not found`)

    const now = new Date().toISOString()
    const phase: ExecutionPhase = {
      id: generateId("exec-phase"),
      name: "Execution Stages",
      order: plan.phases.length + 1,
      stages: stages.map((s, i) => ({
        id: generateId("exec-stage"),
        name: s,
        order: i + 1,
        status: "pending" as ExecutionState,
        startedAt: null,
        completedAt: null,
        durationMs: null,
        error: null,
      })),
      status: "pending" as ExecutionState,
      startedAt: null,
      completedAt: null,
    }
    plan.phases.push(phase)
    plan.updatedAt = now
    return plan
  },

  async groupTasks(planId: string, tasks: DistributedTask[], parallel: boolean = true): Promise<ExecutionBatch> {
    const plan = decompositionPlans.get(planId)
    if (!plan) throw new Error(`Plan ${planId} not found`)

    const batch = {
      id: generateId("exec-batch"),
      sessionId: plan.sessionId,
      phaseId: plan.phases[plan.phases.length - 1]?.id ?? "",
      taskGroups: [{
        id: generateId("exec-task-group"),
        batchId: "",
        name: `Task Group ${Date.now()}`,
        tasks,
        parallel,
        status: "pending" as ExecutionState,
        createdAt: new Date().toISOString(),
        completedAt: null,
      }],
      strategy: plan.distributionStrategy,
      status: "pending" as ExecutionState,
      createdAt: new Date().toISOString(),
      completedAt: null,
    }
    batch.taskGroups[0].batchId = batch.id
    plan.totalTasks += tasks.length
    return batch
  },

  async identifyDependencies(sessionId: string, tasks: DistributedTask[]): Promise<ExecutionDependency[]> {
    const deps: ExecutionDependency[] = []
    const now = new Date().toISOString()

    for (const task of tasks) {
      for (const depId of task.dependencies) {
        const dep: ExecutionDependency = {
          id: generateId("exec-dep"),
          sessionId,
          sourceTaskId: depId,
          targetTaskId: task.id,
          type: "hard",
          resolved: false,
          createdAt: now,
          resolvedAt: null,
        }
        deps.push(dep)
      }
    }
    return deps
  },

  async assignExecutionOrder(planId: string): Promise<ExecutionPlan> {
    const plan = decompositionPlans.get(planId)
    if (!plan) throw new Error(`Plan ${planId} not found`)

    plan.phases.sort((a, b) => a.order - b.order)
    plan.updatedAt = new Date().toISOString()
    return plan
  },

  async getPlan(planId: string): Promise<ExecutionPlan | null> {
    return decompositionPlans.get(planId) ?? null
  },

  defaultPhases(): { name: string; tasks: { name: string; description: string; workerType: string; capabilities: string[]; priority: number }[] }[] {
    return [
      {
        name: "Analysis",
        tasks: [
          { name: "Context Assembly", description: "Assemble execution context", workerType: "intelligence", capabilities: ["analysis"], priority: 1 },
          { name: "Resource Identification", description: "Identify required resources", workerType: "intelligence", capabilities: ["planning"], priority: 2 },
        ],
      },
      {
        name: "Preparation",
        tasks: [
          { name: "Worker Readiness", description: "Verify worker availability", workerType: "orchestrator", capabilities: ["coordination"], priority: 1 },
          { name: "Data Assembly", description: "Assemble required data", workerType: "intelligence", capabilities: ["analysis"], priority: 2 },
        ],
      },
      {
        name: "Execution",
        tasks: [],
      },
      {
        name: "Finalization",
        tasks: [
          { name: "Result Compilation", description: "Compile execution results", workerType: "intelligence", capabilities: ["summary"], priority: 1 },
          { name: "State Persistence", description: "Persist final state", workerType: "orchestrator", capabilities: ["state"], priority: 2 },
        ],
      },
    ]
  },
}
