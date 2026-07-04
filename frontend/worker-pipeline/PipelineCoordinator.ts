import type { PipelineState, PipelineExecution, StageInput } from "./types"
import { PipelineRegistry } from "./PipelineRegistry"
import { PipelineBuilder } from "./PipelineBuilder"
import { StageExecutor } from "./StageExecutor"
import { PipelineContextManager } from "./PipelineContextManager"
import { PipelineCheckpointManager } from "./PipelineCheckpointManager"
import { PipelineMetricsCollector } from "./PipelineMetricsCollector"
import { PipelineValidator } from "./PipelineValidator"
import { generateId } from "@/worker-framework/shared"

const executions = new Map<string, PipelineExecution>()

const stateTransitions: Record<PipelineState, PipelineState[]> = {
  pending: ["building", "cancelled"],
  building: ["ready", "failed", "cancelled"],
  ready: ["running", "cancelled"],
  running: ["paused", "completed", "failed", "cancelled"],
  paused: ["running", "cancelled"],
  completed: [],
  failed: [],
  cancelled: [],
}

export const PipelineCoordinator = {
  async createExecution(pipelineId: string, sessionId: string, correlationId: string, variables?: Record<string, unknown>): Promise<PipelineExecution> {
    const definition = await PipelineRegistry.get(pipelineId)
    if (!definition) {
      throw new Error(`Pipeline ${pipelineId} is not registered`)
    }

    const executionId = generateId("pipeline-exec")
    const context = await PipelineContextManager.createContext(pipelineId, executionId, sessionId, correlationId, variables)

    const execution: PipelineExecution = {
      id: executionId,
      pipelineId,
      state: "pending",
      currentStageId: null,
      stageResults: [],
      context,
      error: null,
      startedAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      completedAt: null,
    }

    executions.set(executionId, execution)
    return execution
  },

  async build(executionId: string): Promise<PipelineExecution> {
    const execution = executions.get(executionId)
    if (!execution) {
      throw new Error(`Execution ${executionId} not found`)
    }

    await this.transitionState(executionId, "building")
    const validation = await PipelineValidator.validatePipeline(execution.pipelineId)
    if (!validation.valid) {
      execution.state = "failed"
      execution.error = {
        code: "PIPELINE_VALIDATION_FAILED",
        message: validation.errors.join("; "),
        module: "PipelineCoordinator",
        severity: "error",
        timestamp: new Date().toISOString(),
        details: { pipelineId: execution.pipelineId, errors: validation.errors },
        cause: null,
      }
      return execution
    }

    execution.state = "ready"
    execution.updatedAt = new Date().toISOString()
    return execution
  },

  async advance(executionId: string): Promise<PipelineExecution> {
    const execution = executions.get(executionId)
    if (!execution) {
      throw new Error(`Execution ${executionId} not found`)
    }

    await this.transitionState(executionId, "running")

    const readyStages = await PipelineBuilder.getReadyStages(execution.pipelineId, execution.context.completedStageIds)

    if (readyStages.length === 0) {
      execution.state = "completed"
      execution.completedAt = new Date().toISOString()
      execution.updatedAt = new Date().toISOString()

      await PipelineMetricsCollector.collect(execution.pipelineId, executionId, execution)
      return execution
    }

    for (const stage of readyStages) {
      execution.currentStageId = stage.id

      const previousOutput = execution.context.completedStageIds.length > 0
        ? execution.stageResults.find((r) => r.stageId === execution.context.completedStageIds[execution.context.completedStageIds.length - 1])?.output?.data ?? null
        : null

      const stageInput: StageInput = {
        stageId: stage.id,
        executionId,
        context: execution.context,
        payload: execution.context.variables,
        previousStageOutput: previousOutput,
      }

      const result = await StageExecutor.executeWithRetry(stage, stageInput)
      execution.stageResults.push(result)
      execution.context = await PipelineContextManager.afterStage(execution.context, stage.id, result)

      if (result.status === "failed") {
        execution.state = "failed"
        execution.error = result.error
        execution.updatedAt = new Date().toISOString()
        return execution
      }
    }

    execution.currentStageId = null
    execution.updatedAt = new Date().toISOString()

    const remainingStages = await PipelineBuilder.getReadyStages(execution.pipelineId, execution.context.completedStageIds)
    if (remainingStages.length === 0) {
      execution.state = "completed"
      execution.completedAt = new Date().toISOString()
    }

    return execution
  },

  async pause(executionId: string): Promise<PipelineExecution> {
    const execution = executions.get(executionId)
    if (!execution) {
      throw new Error(`Execution ${executionId} not found`)
    }

    await this.transitionState(executionId, "paused")
    await PipelineCheckpointManager.save(execution.pipelineId, executionId, execution.state, execution.context, execution.stageResults)
    return execution
  },

  async resume(executionId: string): Promise<PipelineExecution> {
    const execution = executions.get(executionId)
    if (!execution) {
      throw new Error(`Execution ${executionId} not found`)
    }

    await this.transitionState(executionId, "running")

    const readyStages = await PipelineBuilder.getReadyStages(execution.pipelineId, execution.context.completedStageIds)
    if (readyStages.length === 0) {
      execution.state = "completed"
      execution.completedAt = new Date().toISOString()
    }

    execution.updatedAt = new Date().toISOString()
    return execution
  },

  async cancel(executionId: string): Promise<PipelineExecution> {
    const execution = executions.get(executionId)
    if (!execution) {
      throw new Error(`Execution ${executionId} not found`)
    }

    await this.transitionState(executionId, "cancelled")
    execution.completedAt = new Date().toISOString()
    execution.updatedAt = new Date().toISOString()
    return execution
  },

  async getExecution(executionId: string): Promise<PipelineExecution | null> {
    return executions.get(executionId) ?? null
  },

  async listExecutions(pipelineId?: string): Promise<PipelineExecution[]> {
    const all = Array.from(executions.values())
    return pipelineId ? all.filter((e) => e.pipelineId === pipelineId) : all
  },

  async transitionState(executionId: string, target: PipelineState): Promise<void> {
    const execution = executions.get(executionId)
    if (!execution) {
      throw new Error(`Execution ${executionId} not found`)
    }

    const allowed = stateTransitions[execution.state]
    if (!allowed?.includes(target)) {
      throw new Error(`Invalid pipeline state transition: ${execution.state} → ${target}`)
    }

    execution.state = target
    execution.updatedAt = new Date().toISOString()
  },
}
