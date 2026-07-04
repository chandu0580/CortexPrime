import type { PipelineStage } from "./types"
import { PipelineRegistry } from "./PipelineRegistry"

const stages = new Map<string, Map<string, PipelineStage>>()

export const PipelineBuilder = {
  async addStage(pipelineId: string, stage: PipelineStage): Promise<void> {
    const definition = await PipelineRegistry.get(pipelineId)
    if (!definition) {
      throw new Error(`Pipeline ${pipelineId} is not registered`)
    }

    if (!stages.has(pipelineId)) {
      stages.set(pipelineId, new Map())
    }

    const pipelineStages = stages.get(pipelineId)!
    if (pipelineStages.has(stage.id)) {
      throw new Error(`Stage ${stage.id} already exists in pipeline ${pipelineId}`)
    }

    for (const depId of stage.dependencies) {
      if (!pipelineStages.has(depId) && depId !== stage.id) {
        const depExists = await PipelineRegistry.get(pipelineId)
        if (!depExists) {
          throw new Error(`Dependency stage ${depId} not found in pipeline ${pipelineId}`)
        }
      }
    }

    pipelineStages.set(stage.id, { ...stage })
  },

  async removeStage(pipelineId: string, stageId: string): Promise<void> {
    const pipelineStages = stages.get(pipelineId)
    if (!pipelineStages?.has(stageId)) {
      throw new Error(`Stage ${stageId} not found in pipeline ${pipelineId}`)
    }

    const dependentStages = Array.from(pipelineStages.values()).filter((s) => s.dependencies.includes(stageId))
    if (dependentStages.length > 0) {
      throw new Error(
        `Cannot remove stage ${stageId}: ${dependentStages.length} stage(s) depend on it: ${dependentStages.map((s) => s.id).join(", ")}`,
      )
    }

    pipelineStages.delete(stageId)
  },

  async getStages(pipelineId: string): Promise<PipelineStage[]> {
    const pipelineStages = stages.get(pipelineId)
    if (!pipelineStages) {
      return []
    }
    return Array.from(pipelineStages.values()).sort((a, b) => a.order - b.order)
  },

  async getStage(pipelineId: string, stageId: string): Promise<PipelineStage | null> {
    return stages.get(pipelineId)?.get(stageId) ?? null
  },

  async getDependencyOrder(pipelineId: string): Promise<string[]> {
    const pipelineStages = stages.get(pipelineId)
    if (!pipelineStages) {
      return []
    }

    const allStages = Array.from(pipelineStages.values())
    const visited = new Set<string>()
    const visiting = new Set<string>()
    const order: string[] = []

    function visit(stageId: string): void {
      if (visited.has(stageId)) return
      if (visiting.has(stageId)) {
        throw new Error(`Circular dependency detected involving stage ${stageId}`)
      }

      visiting.add(stageId)
      const stage = pipelineStages!.get(stageId)
      if (stage) {
        for (const dep of stage.dependencies) {
          if (pipelineStages!.has(dep)) {
            visit(dep)
          }
        }
      }
      visiting.delete(stageId)
      visited.add(stageId)
      order.push(stageId)
    }

    for (const stage of allStages) {
      visit(stage.id)
    }

    return order
  },

  async getReadyStages(pipelineId: string, completedStageIds: string[]): Promise<PipelineStage[]> {
    const pipelineStages = stages.get(pipelineId)
    if (!pipelineStages) {
      return []
    }

    const allStages = Array.from(pipelineStages.values())
    return allStages.filter((stage) => {
      if (completedStageIds.includes(stage.id)) return false
      return stage.dependencies.every((depId) => completedStageIds.includes(depId))
    })
  },

  async clearStages(pipelineId: string): Promise<void> {
    stages.delete(pipelineId)
  },
}
