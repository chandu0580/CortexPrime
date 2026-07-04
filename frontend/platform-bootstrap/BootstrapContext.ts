import type { BootstrapContext as BootstrapContextDef } from "./types"
import { generateId } from "./shared"

const contexts = new Map<string, BootstrapContextDef>()

export const BootstrapContext = {
  async create(sessionId: string, data: Record<string, unknown> = {}): Promise<BootstrapContextDef> {
    const id = generateId("bctx")
    const context: BootstrapContextDef = {
      id, sessionId, data, version: 1,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }
    contexts.set(id, context)
    return context
  },

  async get(contextId: string): Promise<BootstrapContextDef | null> {
    return contexts.get(contextId) ?? null
  },

  async merge(contextId: string, updates: Record<string, unknown>): Promise<BootstrapContextDef | null> {
    const context = contexts.get(contextId)
    if (!context) return null
    const updated: BootstrapContextDef = {
      ...context, data: { ...context.data, ...updates },
      version: context.version + 1,
      updatedAt: new Date().toISOString(),
    }
    contexts.set(contextId, updated)
    return updated
  },

  async snapshot(contextId: string): Promise<BootstrapContextDef | null> {
    const context = contexts.get(contextId)
    if (!context) return null
    return { ...context, id: generateId("bctx"), createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() }
  },

  async restore(context: BootstrapContextDef): Promise<BootstrapContextDef> {
    const id = generateId("bctx")
    const restored: BootstrapContextDef = {
      ...context, id, version: context.version + 1,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }
    contexts.set(id, restored)
    return restored
  },
}
