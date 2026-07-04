import type { PipelineStage, PipelineExecution, PipelineContext, StageInput, StageResult } from "./types"
import { PipelineRegistry } from "./PipelineRegistry"
import { PipelineBuilder } from "./PipelineBuilder"

interface ValidationResult {
  valid: boolean
  errors: string[]
  warnings: string[]
}

export const PipelineValidator = {
  async validatePipeline(pipelineId: string): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    const definition = await PipelineRegistry.get(pipelineId)
    if (!definition) {
      errors.push(`Pipeline ${pipelineId} is not registered`)
      return { valid: false, errors, warnings }
    }

    if (!definition.id) errors.push("Pipeline ID is required")
    if (!definition.name) errors.push("Pipeline name is required")
    if (definition.stages.length === 0) warnings.push("Pipeline has no stages defined")

    const stages = await PipelineBuilder.getStages(pipelineId)
    if (stages.length === 0 && definition.stages.length > 0) {
      errors.push(`${definition.stages.length} stages listed in definition but none built`)
    }

    if (stages.length > 0) {
      const stageIds = new Set(stages.map((s) => s.id))
      const listedInDef = new Set(definition.stages)

      for (const stageId of definition.stages) {
        if (!stageIds.has(stageId)) {
          errors.push(`Stage ${stageId} is listed in pipeline definition but not built`)
        }
      }

      for (const stage of stages) {
        if (!listedInDef.has(stage.id)) {
          warnings.push(`Stage ${stage.id} is built but not listed in pipeline definition`)
        }
      }

      for (const stage of stages) {
        for (const dep of stage.dependencies) {
          if (!stageIds.has(dep)) {
            errors.push(`Stage ${stage.id} depends on ${dep} which does not exist`)
          }
        }
      }

      if (definition.timeoutMs <= 0) {
        errors.push("Pipeline timeout must be greater than 0")
      }
    }

    return {
      valid: errors.length === 0,
      errors,
      warnings,
    }
  },

  async validateStage(stage: PipelineStage): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    if (!stage.id) errors.push("Stage ID is required")
    if (!stage.name) errors.push("Stage name is required")
    if (!stage.pipelineId) errors.push("Stage pipelineId is required")
    if (stage.order < 0) errors.push("Stage order must be non-negative")
    if (stage.timeoutMs <= 0) warnings.push("Stage timeout is not set, using default")

    return {
      valid: errors.length === 0,
      errors,
      warnings,
    }
  },

  async validateExecution(execution: PipelineExecution): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    if (!execution.id) errors.push("Execution ID is required")
    if (!execution.pipelineId) errors.push("Execution pipelineId is required")

    const definition = await PipelineRegistry.get(execution.pipelineId)
    if (definition && execution.stageResults.length > 0) {
      const stages = await PipelineBuilder.getStages(execution.pipelineId)
      const stageIds = new Set(stages.map((s) => s.id))

      for (const result of execution.stageResults) {
        if (!stageIds.has(result.stageId)) {
          warnings.push(`Execution has result for stage ${result.stageId} which is not in the pipeline`)
        }
      }
    }

    if (execution.state === "completed" && execution.completedAt === null) {
      errors.push("Completed execution must have a completedAt timestamp")
    }

    return {
      valid: errors.length === 0,
      errors,
      warnings,
    }
  },

  async validateStageInput(input: StageInput): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    if (!input.stageId) errors.push("StageInput stageId is required")
    if (!input.executionId) errors.push("StageInput executionId is required")
    if (!input.context) errors.push("StageInput context is required")

    if (input.context && input.context.completedStageIds.includes(input.stageId)) {
      errors.push(`Stage ${input.stageId} has already been completed`)
    }

    return {
      valid: errors.length === 0,
      errors,
      warnings,
    }
  },

  async validateStageResult(result: StageResult): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    if (!result.stageId) errors.push("StageResult stageId is required")
    if (!result.status) errors.push("StageResult status is required")
    if (result.durationMs < 0) errors.push("StageResult durationMs must be non-negative")

    if (result.status === "completed" && !result.output) {
      warnings.push("Completed stage result has no output")
    }

    if (result.status === "failed" && !result.error) {
      warnings.push("Failed stage result has no error details")
    }

    return {
      valid: errors.length === 0,
      errors,
      warnings,
    }
  },

  async validateContext(context: PipelineContext): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    if (!context.pipelineId) errors.push("Context pipelineId is required")
    if (!context.executionId) errors.push("Context executionId is required")
    if (!context.sessionId) errors.push("Context sessionId is required")
    if (!context.correlationId) errors.push("Context correlationId is required")

    return {
      valid: errors.length === 0,
      errors,
      warnings,
    }
  },
}
