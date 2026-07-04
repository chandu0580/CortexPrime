import type { WorkerSynchronization, WorkerBarrier, SynchronizationStrategy } from "./types"
import { generateId } from "@/worker-framework/shared"

const synchronizations = new Map<string, WorkerSynchronization>()
const barriers = new Map<string, WorkerBarrier>()

export const WorkerSynchronizationEngine = {
  async createBarrier(sessionId: string, name: string, participantIds: string[]): Promise<WorkerBarrier> {
    const barrier: WorkerBarrier = {
      id: generateId("wo-barrier"),
      sessionId,
      name,
      participantIds,
      arrivedIds: [],
      released: false,
      createdAt: new Date().toISOString(),
      releasedAt: null,
    }
    barriers.set(barrier.id, barrier)
    return barrier
  },

  async getBarrier(barrierId: string): Promise<WorkerBarrier | null> {
    return barriers.get(barrierId) ?? null
  },

  async waitForBarrier(barrierId: string, workerId: string): Promise<boolean> {
    const barrier = barriers.get(barrierId)
    if (!barrier) throw new Error(`Barrier ${barrierId} not found`)
    if (barrier.released) return true

    if (!barrier.arrivedIds.includes(workerId)) {
      barrier.arrivedIds.push(workerId)
    }

    if (barrier.arrivedIds.length >= barrier.participantIds.length) {
      barrier.released = true
      barrier.releasedAt = new Date().toISOString()
      return true
    }
    return false
  },

  async releaseBarrier(barrierId: string): Promise<WorkerBarrier> {
    const barrier = barriers.get(barrierId)
    if (!barrier) throw new Error(`Barrier ${barrierId} not found`)
    barrier.released = true
    barrier.releasedAt = new Date().toISOString()
    return barrier
  },

  async createSynchronization(sessionId: string, groupId: string, type: SynchronizationStrategy, participantCount: number): Promise<WorkerSynchronization> {
    const sync: WorkerSynchronization = {
      id: generateId("wo-sync"),
      sessionId,
      groupId,
      type,
      status: "pending",
      participantCount,
      readyCount: 0,
      createdAt: new Date().toISOString(),
      completedAt: null,
    }
    synchronizations.set(sync.id, sync)
    return sync
  },

  async synchronizeWorkers(syncId: string): Promise<WorkerSynchronization> {
    const sync = synchronizations.get(syncId)
    if (!sync) throw new Error(`Synchronization ${syncId} not found`)

    sync.status = "syncing"
    sync.readyCount++

    if (sync.readyCount >= sync.participantCount) {
      sync.status = "synced"
      sync.completedAt = new Date().toISOString()
    }

    return sync
  },

  async getSynchronization(syncId: string): Promise<WorkerSynchronization | null> {
    return synchronizations.get(syncId) ?? null
  },

  async getSynchronizationsBySession(sessionId: string): Promise<WorkerSynchronization[]> {
    return Array.from(synchronizations.values()).filter((s) => s.sessionId === sessionId)
  },

  async getBarriersBySession(sessionId: string): Promise<WorkerBarrier[]> {
    return Array.from(barriers.values()).filter((b) => b.sessionId === sessionId)
  },

  async countCompleted(): Promise<number> {
    return Array.from(synchronizations.values()).filter((s) => s.status === "synced").length
  },

  async clearSession(sessionId: string): Promise<void> {
    for (const [id, s] of synchronizations.entries()) {
      if (s.sessionId === sessionId) synchronizations.delete(id)
    }
    for (const [id, b] of barriers.entries()) {
      if (b.sessionId === sessionId) barriers.delete(id)
    }
  },
}
