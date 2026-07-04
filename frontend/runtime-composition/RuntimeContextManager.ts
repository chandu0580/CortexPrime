import type { RuntimeContext } from "./types"
import { generateId } from "./shared"

const contexts = new Map<string, RuntimeContext>()

export const RuntimeContextManager = {
  async create(compositionId: string, data: Record<string, unknown> = {}): Promise<RuntimeContext> {
    const id = generateId("rtctx")
    const ctx: RuntimeContext = {
      id, compositionId, data, version: 1,
      createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(),
    }
    contexts.set(id, ctx)
    return ctx
  },

  async get(contextId: string): Promise<RuntimeContext | null> {
    return contexts.get(contextId) ?? null
  },

  async merge(contextId: string, updates: Record<string, unknown>): Promise<RuntimeContext | null> {
    const ctx = contexts.get(contextId)
    if (!ctx) return null
    const updated: RuntimeContext = {
      ...ctx, data: { ...ctx.data, ...updates },
      version: ctx.version + 1, updatedAt: new Date().toISOString(),
    }
    contexts.set(contextId, updated)
    return updated
  },

  async snapshot(contextId: string): Promise<RuntimeContext | null> {
    const ctx = contexts.get(contextId)
    if (!ctx) return null
    return { ...ctx, id: generateId("rtctx"), createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() }
  },

  async restore(context: RuntimeContext): Promise<RuntimeContext> {
    const id = generateId("rtctx")
    const restored: RuntimeContext = { ...context, id, version: context.version + 1, createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() }
    contexts.set(id, restored)
    return restored
  },
}
