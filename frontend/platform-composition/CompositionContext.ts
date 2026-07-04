import type { CompositionContext } from "./types"
import { generateId } from "./shared"

const contexts = new Map<string, CompositionContext>()

export const CompositionContextManager = {
  async createContext(compositionId: string, initial: Record<string, unknown> = {}): Promise<CompositionContext> {
    const id = generateId("ctx")
    const context: CompositionContext = {
      id, compositionId, state: { ...initial }, version: 1, createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(),
    }
    contexts.set(id, context)
    return context
  },

  async getContext(contextId: string): Promise<CompositionContext | null> {
    return contexts.get(contextId) ?? null
  },

  async getContextsByComposition(compositionId: string): Promise<CompositionContext[]> {
    return Array.from(contexts.values()).filter((c) => c.compositionId === compositionId)
  },

  async updateContext(contextId: string, updates: Record<string, unknown>): Promise<CompositionContext | null> {
    const context = contexts.get(contextId)
    if (!context) return null
    const updated: CompositionContext = {
      ...context, state: { ...context.state, ...updates }, version: context.version + 1, updatedAt: new Date().toISOString(),
    }
    contexts.set(contextId, updated)
    return updated
  },

  async snapshot(contextId: string): Promise<CompositionContext | null> {
    const context = contexts.get(contextId)
    if (!context) return null
    return { ...context, id: generateId("ctx"), version: context.version, createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() }
  },

  async restore(context: CompositionContext): Promise<CompositionContext> {
    const id = generateId("ctx")
    const restored: CompositionContext = { ...context, id, version: context.version + 1, createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() }
    contexts.set(id, restored)
    return restored
  },

  async merge(contextId: string, other: Record<string, unknown>): Promise<CompositionContext | null> {
    const context = contexts.get(contextId)
    if (!context) return null
    return this.updateContext(contextId, { ...context.state, ...other })
  },
}