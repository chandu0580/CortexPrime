import type { DeferredExecution } from "./types"
import { generateId } from "./shared"

const deferred = new Map<string, DeferredExecution>()

export const DeferredExecutionManager = {
  async defer(
    originalScheduleId: string,
    deferredUntil: string,
    reason: string,
    autoResume: boolean = true,
  ): Promise<DeferredExecution> {
    const entry: DeferredExecution = {
      id: generateId("deferred"),
      originalScheduleId,
      deferredUntil,
      reason,
      autoResume,
      resumedAt: null,
    }
    deferred.set(entry.id, entry)
    return entry
  },

  async getDeferred(id: string): Promise<DeferredExecution | null> {
    return deferred.get(id) ?? null
  },

  async resume(id: string): Promise<DeferredExecution> {
    const entry = deferred.get(id)
    if (!entry) throw new Error(`Deferred execution not found: ${id}`)
    const updated: DeferredExecution = {
      ...entry,
      resumedAt: new Date().toISOString(),
    }
    deferred.set(id, updated)
    return updated
  },

  async getDueDeferred(): Promise<DeferredExecution[]> {
    const now = new Date()
    return Array.from(deferred.values()).filter(
      (d) => d.resumedAt === null && new Date(d.deferredUntil) <= now,
    )
  },

  async getPendingDeferred(): Promise<DeferredExecution[]> {
    return Array.from(deferred.values()).filter((d) => d.resumedAt === null)
  },

  async cancelDeferred(id: string): Promise<void> {
    deferred.delete(id)
  },

  async getDeferredCount(): Promise<number> {
    return deferred.size
  },
}
