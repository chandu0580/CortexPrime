import type { PipelineContext, StageResult } from "./types"

export const PipelineContextManager = {
  async createContext(
    pipelineId: string,
    executionId: string,
    sessionId: string,
    correlationId: string,
    variables?: Record<string, unknown>,
  ): Promise<PipelineContext> {
    return {
      pipelineId,
      executionId,
      sessionId,
      correlationId,
      currentStageId: null,
      completedStageIds: [],
      variables: variables ?? {},
      metadata: {},
      startedAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }
  },

  async afterStage(
    context: PipelineContext,
    stageId: string,
    result: StageResult,
  ): Promise<PipelineContext> {
    const updatedVariables = { ...context.variables }

    if (result.output?.data) {
      for (const [key, value] of Object.entries(result.output.data)) {
        updatedVariables[`stage.${stageId}.${key}`] = value
      }
    }

    return {
      ...context,
      currentStageId: null,
      completedStageIds: [...context.completedStageIds, stageId],
      variables: updatedVariables,
      updatedAt: new Date().toISOString(),
    }
  },

  async setVariable(context: PipelineContext, key: string, value: unknown): Promise<PipelineContext> {
    return {
      ...context,
      variables: { ...context.variables, [key]: value },
      updatedAt: new Date().toISOString(),
    }
  },

  async getVariable(context: PipelineContext, key: string): Promise<unknown> {
    return context.variables[key]
  },

  async setMetadata(context: PipelineContext, key: string, value: string): Promise<PipelineContext> {
    return {
      ...context,
      metadata: { ...context.metadata, [key]: value },
      updatedAt: new Date().toISOString(),
    }
  },

  async mergeContext(base: PipelineContext, overlay: Partial<PipelineContext>): Promise<PipelineContext> {
    return {
      ...base,
      ...overlay,
      variables: { ...base.variables, ...(overlay.variables ?? {}) },
      metadata: { ...base.metadata, ...(overlay.metadata ?? {}) },
      completedStageIds: [...new Set([...base.completedStageIds, ...(overlay.completedStageIds ?? [])])],
      updatedAt: new Date().toISOString(),
    }
  },
}
