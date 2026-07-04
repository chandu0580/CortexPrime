import type { WorkerContext } from "./types"
import type { PlatformContext } from "@/platform/contracts"

const contexts = new Map<string, WorkerContext>()

export const WorkerContextManager = {
  async initialize(workerId: string): Promise<WorkerContext> {
    const ctx: WorkerContext = {
      currentSessionId: null,
      currentTaskId: null,
      platformContext: null,
      startedAt: new Date().toISOString(),
      lastActivityAt: new Date().toISOString(),
    }
    contexts.set(workerId, ctx)
    return ctx
  },

  async getContext(workerId: string): Promise<WorkerContext | null> {
    return contexts.get(workerId) ?? null
  },

  async setSession(workerId: string, sessionId: string, platformContext: PlatformContext): Promise<WorkerContext> {
    const ctx = contexts.get(workerId)
    if (!ctx) throw new Error(`No context for worker: ${workerId}`)
    const updated: WorkerContext = {
      ...ctx,
      currentSessionId: sessionId,
      platformContext,
      lastActivityAt: new Date().toISOString(),
    }
    contexts.set(workerId, updated)
    return updated
  },

  async setTask(workerId: string, taskId: string): Promise<WorkerContext> {
    const ctx = contexts.get(workerId)
    if (!ctx) throw new Error(`No context for worker: ${workerId}`)
    const updated: WorkerContext = {
      ...ctx,
      currentTaskId: taskId,
      lastActivityAt: new Date().toISOString(),
    }
    contexts.set(workerId, updated)
    return updated
  },

  async clearSession(workerId: string): Promise<WorkerContext> {
    const ctx = contexts.get(workerId)
    if (!ctx) throw new Error(`No context for worker: ${workerId}`)
    const updated: WorkerContext = {
      ...ctx,
      currentSessionId: null,
      currentTaskId: null,
      platformContext: null,
      lastActivityAt: new Date().toISOString(),
    }
    contexts.set(workerId, updated)
    return updated
  },

  async touch(workerId: string): Promise<void> {
    const ctx = contexts.get(workerId)
    if (ctx) {
      contexts.set(workerId, { ...ctx, lastActivityAt: new Date().toISOString() })
    }
  },
}
