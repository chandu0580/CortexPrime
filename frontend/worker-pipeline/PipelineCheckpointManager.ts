import type { PipelineCheckpoint, PipelineState, PipelineContext, StageResult } from "./types"
import { generateId } from "@/worker-framework/shared"

const checkpoints = new Map<string, PipelineCheckpoint>()

export const PipelineCheckpointManager = {
  async save(
    pipelineId: string,
    executionId: string,
    state: PipelineState,
    context: PipelineContext,
    stageResults: StageResult[],
    ttlMs: number = 300_000,
  ): Promise<PipelineCheckpoint> {
    const checkpoint: PipelineCheckpoint = {
      id: generateId("pipeline-cp"),
      pipelineId,
      executionId,
      stageId: context.currentStageId ?? "pre-execution",
      state,
      context: { ...context, variables: { ...context.variables }, metadata: { ...context.metadata } },
      stageResults: stageResults.map((r) => ({ ...r })),
      savedAt: new Date().toISOString(),
      expiresAt: new Date(Date.now() + ttlMs).toISOString(),
      version: this.getNextVersion(executionId),
    }

    checkpoints.set(checkpoint.id, checkpoint)
    return checkpoint
  },

  async restore(checkpointId: string): Promise<PipelineCheckpoint | null> {
    const checkpoint = checkpoints.get(checkpointId)
    if (!checkpoint) return null

    if (Date.now() > new Date(checkpoint.expiresAt).getTime()) {
      checkpoints.delete(checkpointId)
      return null
    }

    return checkpoint
  },

  async delete(checkpointId: string): Promise<void> {
    checkpoints.delete(checkpointId)
  },

  async list(executionId: string): Promise<PipelineCheckpoint[]> {
    return Array.from(checkpoints.values())
      .filter((cp) => cp.executionId === executionId)
      .sort((a, b) => b.version - a.version)
  },

  async latest(executionId: string): Promise<PipelineCheckpoint | null> {
    const executionCheckpoints = await this.list(executionId)
    return executionCheckpoints[0] ?? null
  },

  async cleanupExpired(): Promise<number> {
    const now = Date.now()
    let count = 0
    for (const [id, cp] of checkpoints.entries()) {
      if (now > new Date(cp.expiresAt).getTime()) {
        checkpoints.delete(id)
        count++
      }
    }
    return count
  },

  getNextVersion(executionId: string): number {
    const existing = Array.from(checkpoints.values()).filter((cp) => cp.executionId === executionId)
    return existing.length + 1
  },
}
