import type { CognitivePipelineDefinition, CognitivePipelineExecution, CognitiveStage, CognitiveStageDef, CognitiveStatus, CoordinationStrategy, RoutingPolicy } from "./types"
import { generateId } from "@/worker-framework/shared"

const pipelineDefinitions = new Map<string, CognitivePipelineDefinition>()
const executions = new Map<string, CognitivePipelineExecution>()

const DEFAULT_STAGES: CognitiveStage[] = [
  "intake",
  "context_build",
  "memory_retrieval",
  "knowledge_resolution",
  "worker_coordination",
  "world_state_update",
  "validation",
  "completion",
]

export const CognitivePipeline = {
  async createDefinition(
    name: string,
    stages: CognitiveStage[] = DEFAULT_STAGES,
    strategy: CoordinationStrategy = "sequential",
    routingPolicy: RoutingPolicy = "auto",
    maxRetries: number = 3,
  ): Promise<CognitivePipelineDefinition> {
    const def: CognitivePipelineDefinition = {
      id: generateId("cog-pipeline"),
      name,
      stages,
      strategy,
      routingPolicy,
      maxRetries,
      enabled: true,
    }
    pipelineDefinitions.set(def.id, def)
    return def
  },

  async getDefinition(pipelineId: string): Promise<CognitivePipelineDefinition | null> {
    return pipelineDefinitions.get(pipelineId) ?? null
  },

  async getAllDefinitions(): Promise<CognitivePipelineDefinition[]> {
    return Array.from(pipelineDefinitions.values())
  },

  async startExecution(pipelineId: string, sessionId: string): Promise<CognitivePipelineExecution> {
    const def = await this.getDefinition(pipelineId)
    if (!def) throw new Error(`Pipeline definition ${pipelineId} not found`)
    if (!def.enabled) throw new Error(`Pipeline ${pipelineId} is disabled`)

    const now = new Date().toISOString()
    const execution: CognitivePipelineExecution = {
      id: generateId("cog-exec"),
      pipelineId,
      sessionId,
      stages: def.stages.map((s, i) => ({
        id: generateId("cog-stage"),
        name: s,
        order: i + 1,
        status: "pending" as CognitiveStatus,
        startedAt: null,
        completedAt: null,
        durationMs: null,
        error: null,
        retryCount: 0,
      })),
      status: "active",
      currentStageIndex: 0,
      startedAt: now,
      completedAt: null,
      durationMs: null,
    }
    executions.set(execution.id, execution)
    return execution
  },

  async getExecution(executionId: string): Promise<CognitivePipelineExecution | null> {
    return executions.get(executionId) ?? null
  },

  async getExecutionBySession(sessionId: string): Promise<CognitivePipelineExecution | null> {
    return Array.from(executions.values()).find((e) => e.sessionId === sessionId) ?? null
  },

  async advanceStage(executionId: string): Promise<CognitivePipelineExecution> {
    const exec = await this.getExecution(executionId)
    if (!exec) throw new Error(`Pipeline execution ${executionId} not found`)

    const nextIndex = exec.currentStageIndex + 1
    if (nextIndex >= exec.stages.length) {
      return this.completeExecution(executionId)
    }

    const updated: CognitivePipelineExecution = {
      ...exec,
      currentStageIndex: nextIndex,
    }
    executions.set(executionId, updated)
    return updated
  },

  async markStageStarted(executionId: string, stageOrder: number): Promise<CognitivePipelineExecution> {
    const exec = await this.getExecution(executionId)
    if (!exec) throw new Error(`Pipeline execution ${executionId} not found`)

    const stages = exec.stages.map((s) =>
      s.order === stageOrder ? { ...s, status: "active" as CognitiveStatus, startedAt: new Date().toISOString() } : s,
    )
    const updated: CognitivePipelineExecution = { ...exec, stages }
    executions.set(executionId, updated)
    return updated
  },

  async markStageCompleted(executionId: string, stageOrder: number): Promise<CognitivePipelineExecution> {
    const exec = await this.getExecution(executionId)
    if (!exec) throw new Error(`Pipeline execution ${executionId} not found`)

    const now = new Date().toISOString()
    const stages = exec.stages.map((s) => {
      if (s.order !== stageOrder) return s
      const started = s.startedAt ? new Date(s.startedAt).getTime() : Date.now()
      return { ...s, status: "completed" as CognitiveStatus, completedAt: now, durationMs: Date.now() - started }
    })
    const updated: CognitivePipelineExecution = { ...exec, stages }
    executions.set(executionId, updated)
    return updated
  },

  async markStageFailed(executionId: string, stageOrder: number, error: string): Promise<CognitivePipelineExecution> {
    const exec = await this.getExecution(executionId)
    if (!exec) throw new Error(`Pipeline execution ${executionId} not found`)

    const now = new Date().toISOString()
    const stages = exec.stages.map((s) => {
      if (s.order !== stageOrder) return s
      const started = s.startedAt ? new Date(s.startedAt).getTime() : Date.now()
      return { ...s, status: "failed" as CognitiveStatus, completedAt: now, durationMs: Date.now() - started, error, retryCount: s.retryCount + 1 }
    })
    const updated: CognitivePipelineExecution = { ...exec, stages }
    executions.set(executionId, updated)
    return updated
  },

  async completeExecution(executionId: string): Promise<CognitivePipelineExecution> {
    const exec = await this.getExecution(executionId)
    if (!exec) throw new Error(`Pipeline execution ${executionId} not found`)

    const now = new Date().toISOString()
    const updated: CognitivePipelineExecution = {
      ...exec,
      status: "completed",
      completedAt: now,
      durationMs: Date.now() - new Date(exec.startedAt).getTime(),
    }
    executions.set(executionId, updated)
    return updated
  },

  async failExecution(executionId: string): Promise<CognitivePipelineExecution> {
    const exec = await this.getExecution(executionId)
    if (!exec) throw new Error(`Pipeline execution ${executionId} not found`)

    const now = new Date().toISOString()
    const updated: CognitivePipelineExecution = {
      ...exec,
      status: "failed",
      completedAt: now,
      durationMs: Date.now() - new Date(exec.startedAt).getTime(),
    }
    executions.set(executionId, updated)
    return updated
  },

  async getCurrentStage(executionId: string): Promise<CognitiveStageDef | null> {
    const exec = await this.getExecution(executionId)
    if (!exec) return null
    return exec.stages[exec.currentStageIndex] ?? null
  },

  async getExecutionsByStatus(status: CognitiveStatus): Promise<CognitivePipelineExecution[]> {
    return Array.from(executions.values()).filter((e) => e.status === status)
  },
}
