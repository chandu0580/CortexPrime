import type { PlatformError } from "@/platform/contracts"
import type { PipelineStage, StageInput, StageResult, StageOutput, StageStatus } from "./types"

export const StageExecutor = {
  async execute(stage: PipelineStage, input: StageInput): Promise<StageResult> {
    const startTime = Date.now()
    const startedAt = new Date(startTime).toISOString()

    let status: StageStatus = "running"
    let output: StageOutput | null = null
    let error: PlatformError | null = null

    try {
      const data = await this.executeStageLogic(stage, input)

      output = {
        stageId: stage.id,
        executionId: input.executionId,
        data,
        metadata: {
          stageName: stage.name,
          pipelineId: stage.pipelineId,
          order: String(stage.order),
        },
        completedAt: new Date().toISOString(),
      }

      status = "completed"
    } catch (err) {
      error = {
        code: "STAGE_EXECUTION_FAILED",
        message: err instanceof Error ? err.message : String(err),
        module: `StageExecutor:${stage.id}`,
        severity: "error",
        timestamp: new Date().toISOString(),
        details: {
          stageId: stage.id,
          stageName: stage.name,
          pipelineId: stage.pipelineId,
          retryCount: stage.retryCount,
          maxRetries: stage.maxRetries,
        },
        cause: null,
      }
      status = "failed"
    }

    return {
      stageId: stage.id,
      status,
      input,
      output,
      error,
      startedAt,
      completedAt: new Date().toISOString(),
      durationMs: Date.now() - startTime,
      retryAttempt: stage.retryCount,
    }
  },

  async executeWithRetry(stage: PipelineStage, input: StageInput): Promise<StageResult> {
    let lastResult: StageResult | null = null

    for (let attempt = 0; attempt <= stage.maxRetries; attempt++) {
      const retryStage: PipelineStage = { ...stage, retryCount: attempt }
      lastResult = await this.execute(retryStage, input)

      if (lastResult.status === "completed") {
        return lastResult
      }

      if (attempt < stage.maxRetries) {
        const delayMs = Math.min(1000 * Math.pow(2, attempt), 10_000)
        await this.delay(delayMs)
      }
    }

    return lastResult!
  },

  async executeStageLogic(stage: PipelineStage, input: StageInput): Promise<Record<string, unknown>> {
    return {
      stageId: stage.id,
      stageName: stage.name,
      pipelineId: stage.pipelineId,
      order: stage.order,
      processed: true,
      inputKeys: Object.keys(input.payload),
      previousStageOutputKeys: input.previousStageOutput ? Object.keys(input.previousStageOutput) : [],
      timestamp: new Date().toISOString(),
    }
  },

  delay(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms))
  },
}
