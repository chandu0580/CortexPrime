import type { CognitiveContext, WorkerResult, CognitiveDecision, CognitiveRequest } from "./types"
import { generateId } from "@/worker-framework/shared"

const contexts = new Map<string, CognitiveContext>()

export const CognitiveContextManager = {
  async createContext(sessionId: string, request: CognitiveRequest): Promise<CognitiveContext> {
    const context: CognitiveContext = {
      id: generateId("cog-context"),
      sessionId,
      request,
      memoryEntries: [],
      knowledgeEntities: [],
      worldStateKeys: [],
      workerResults: [],
      decisions: [],
      metadata: request.metadata ?? {},
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }
    contexts.set(context.id, context)
    return context
  },

  async getContext(contextId: string): Promise<CognitiveContext | null> {
    return contexts.get(contextId) ?? null
  },

  async getContextBySession(sessionId: string): Promise<CognitiveContext | null> {
    return Array.from(contexts.values()).find((c) => c.sessionId === sessionId) ?? null
  },

  async mergeContext(contextId: string, updates: Partial<CognitiveContext>): Promise<CognitiveContext> {
    const context = contexts.get(contextId)
    if (!context) throw new Error(`CognitiveContext ${contextId} not found`)
    const merged: CognitiveContext = { ...context, ...updates, updatedAt: new Date().toISOString() }
    contexts.set(contextId, merged)
    return merged
  },

  async updateContext(contextId: string, field: keyof CognitiveContext, value: unknown): Promise<CognitiveContext> {
    const context = contexts.get(contextId)
    if (!context) throw new Error(`CognitiveContext ${contextId} not found`)
    const updated: CognitiveContext = { ...context, [field]: value, updatedAt: new Date().toISOString() }
    contexts.set(contextId, updated)
    return updated
  },

  async addMemoryEntry(contextId: string, entryId: string): Promise<void> {
    const context = await this.getContext(contextId)
    if (!context) throw new Error(`CognitiveContext ${contextId} not found`)
    if (!context.memoryEntries.includes(entryId)) {
      context.memoryEntries.push(entryId)
      await this.updateContext(contextId, "memoryEntries", context.memoryEntries)
    }
  },

  async addKnowledgeEntity(contextId: string, entityId: string): Promise<void> {
    const context = await this.getContext(contextId)
    if (!context) throw new Error(`CognitiveContext ${contextId} not found`)
    if (!context.knowledgeEntities.includes(entityId)) {
      context.knowledgeEntities.push(entityId)
      await this.updateContext(contextId, "knowledgeEntities", context.knowledgeEntities)
    }
  },

  async addWorldStateKey(contextId: string, key: string): Promise<void> {
    const context = await this.getContext(contextId)
    if (!context) throw new Error(`CognitiveContext ${contextId} not found`)
    if (!context.worldStateKeys.includes(key)) {
      context.worldStateKeys.push(key)
      await this.updateContext(contextId, "worldStateKeys", context.worldStateKeys)
    }
  },

  async addWorkerResult(contextId: string, result: WorkerResult): Promise<void> {
    const context = await this.getContext(contextId)
    if (!context) throw new Error(`CognitiveContext ${contextId} not found`)
    context.workerResults.push(result)
    await this.updateContext(contextId, "workerResults", context.workerResults)
  },

  async addDecision(contextId: string, decision: CognitiveDecision): Promise<void> {
    const context = await this.getContext(contextId)
    if (!context) throw new Error(`CognitiveContext ${contextId} not found`)
    context.decisions.push(decision)
    await this.updateContext(contextId, "decisions", context.decisions)
  },

  async snapshotContext(contextId: string): Promise<CognitiveContext> {
    const context = await this.getContext(contextId)
    if (!context) throw new Error(`CognitiveContext ${contextId} not found`)
    return { ...context, id: `${context.id}-snap-${Date.now()}` }
  },

  async restoreContext(snapshot: CognitiveContext): Promise<CognitiveContext> {
    const restored: CognitiveContext = {
      ...snapshot,
      id: generateId("cog-context-restored"),
      updatedAt: new Date().toISOString(),
    }
    contexts.set(restored.id, restored)
    return restored
  },

  async clearSession(sessionId: string): Promise<void> {
    for (const [id, ctx] of contexts.entries()) {
      if (ctx.sessionId === sessionId) contexts.delete(id)
    }
  },
}
