import type { PipelineDefinition } from "./types"

const registry = new Map<string, PipelineDefinition>()

export const PipelineRegistry = {
  async register(definition: PipelineDefinition): Promise<void> {
    if (registry.has(definition.id)) {
      throw new Error(`Pipeline ${definition.id} is already registered`)
    }
    registry.set(definition.id, { ...definition })
  },

  async unregister(pipelineId: string): Promise<void> {
    if (!registry.has(pipelineId)) {
      throw new Error(`Pipeline ${pipelineId} is not registered`)
    }
    registry.delete(pipelineId)
  },

  async get(pipelineId: string): Promise<PipelineDefinition | null> {
    return registry.get(pipelineId) ?? null
  },

  async list(): Promise<PipelineDefinition[]> {
    return Array.from(registry.values())
  },

  async findByTag(tag: string): Promise<PipelineDefinition[]> {
    return Array.from(registry.values()).filter((p) => p.tags.includes(tag))
  },

  async exists(pipelineId: string): Promise<boolean> {
    return registry.has(pipelineId)
  },

  async count(): Promise<number> {
    return registry.size
  },
}
