import type { PlatformMetadata, PlatformCapability } from "@/platform/contracts"
import type { PipelineDefinition, PipelineStage, PipelineExecution, PipelineCheckpoint, PipelineMetrics, StageInput, StageResult } from "./types"
import { PipelineRegistry } from "./PipelineRegistry"
import { PipelineBuilder } from "./PipelineBuilder"
import { StageExecutor } from "./StageExecutor"
import { PipelineCoordinator } from "./PipelineCoordinator"
import { PipelineCheckpointManager } from "./PipelineCheckpointManager"
import { PipelineMetricsCollector } from "./PipelineMetricsCollector"
import { PipelineValidator } from "./PipelineValidator"

export abstract class AbstractPipeline {
  protected abstract pipelineId: string
  protected abstract pipelineName: string
  protected abstract pipelineVersion: string
  protected abstract pipelineDescription: string
  protected abstract pipelineTags: string[]
  protected abstract pipelineTimeoutMs: number
  protected abstract pipelineMaxRetries: number

  abstract getCapabilities(): PlatformCapability[]

  async registerPipeline(): Promise<void> {
    const definition: PipelineDefinition = {
      id: this.pipelineId,
      name: this.pipelineName,
      description: this.pipelineDescription,
      version: this.pipelineVersion,
      stages: [],
      tags: [...this.pipelineTags],
      timeoutMs: this.pipelineTimeoutMs,
      maxRetries: this.pipelineMaxRetries,
      createdBy: "AbstractPipeline",
      createdAt: new Date().toISOString(),
    }
    await PipelineRegistry.register(definition)
  }

  abstract build(): Promise<void>

  async executeStage(stageId: string, input: StageInput): Promise<StageResult> {
    const stage = await PipelineBuilder.getStage(this.pipelineId, stageId)
    if (!stage) {
      throw new Error(`Stage ${stageId} not found in pipeline ${this.pipelineId}`)
    }
    return StageExecutor.executeWithRetry(stage, input)
  }

  async advance(executionId: string): Promise<PipelineExecution> {
    return PipelineCoordinator.advance(executionId)
  }

  async pause(executionId: string): Promise<PipelineExecution> {
    return PipelineCoordinator.pause(executionId)
  }

  async resume(executionId: string): Promise<PipelineExecution> {
    return PipelineCoordinator.resume(executionId)
  }

  async cancel(executionId: string): Promise<PipelineExecution> {
    return PipelineCoordinator.cancel(executionId)
  }

  async checkpoint(executionId: string, ttlMs?: number): Promise<PipelineCheckpoint> {
    const execution = await PipelineCoordinator.getExecution(executionId)
    if (!execution) {
      throw new Error(`Execution ${executionId} not found`)
    }
    return PipelineCheckpointManager.save(
      execution.pipelineId,
      executionId,
      execution.state,
      execution.context,
      execution.stageResults,
      ttlMs,
    )
  }

  async validate(): Promise<{ valid: boolean; errors: string[]; warnings: string[] }> {
    return PipelineValidator.validatePipeline(this.pipelineId)
  }

  async collectMetrics(executionId: string): Promise<PipelineMetrics | null> {
    const execution = await PipelineCoordinator.getExecution(executionId)
    if (!execution) return null
    return PipelineMetricsCollector.collect(this.pipelineId, executionId, execution)
  }

  protected async createExecution(sessionId: string, correlationId: string, variables?: Record<string, unknown>): Promise<PipelineExecution> {
    return PipelineCoordinator.createExecution(this.pipelineId, sessionId, correlationId, variables)
  }

  protected async getExecution(executionId: string): Promise<PipelineExecution | null> {
    return PipelineCoordinator.getExecution(executionId)
  }

  protected async getDefinition(): Promise<PipelineDefinition | null> {
    return PipelineRegistry.get(this.pipelineId)
  }

  protected async addStage(stage: PipelineStage): Promise<void> {
    await PipelineBuilder.addStage(this.pipelineId, stage)
  }

  protected async getStages(): Promise<PipelineStage[]> {
    return PipelineBuilder.getStages(this.pipelineId)
  }

  protected async getPipelineMetadata(): Promise<PlatformMetadata> {
    return {
      key: `pipeline.${this.pipelineId}`,
      value: `${this.pipelineName} v${this.pipelineVersion}`,
      tags: [...this.pipelineTags, `pipeline:${this.pipelineId}`],
      createdAt: new Date().toISOString(),
    }
  }
}
