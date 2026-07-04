import type { SynchronizationBarrier, SynchronizationMode } from "./types"
import { generateId } from "./shared"

const barriers = new Map<string, SynchronizationBarrier>()

export const SynchronizationEngine = {
  async createBarrier(sessionId: string, name: string, mode: SynchronizationMode, requiredWorkers: string[]): Promise<SynchronizationBarrier> {
    const id = generateId("barrier")
    const barrier: SynchronizationBarrier = {
      id,
      sessionId,
      name,
      mode,
      requiredWorkers,
      arrivedWorkers: [],
      state: "waiting",
      createdAt: new Date().toISOString(),
      releasedAt: null,
    }
    barriers.set(id, barrier)
    return barrier
  },

  async synchronizeWorkers(barrierId: string, workerId: string): Promise<SynchronizationBarrier> {
    const barrier = barriers.get(barrierId)
    if (!barrier) throw new Error(`Barrier not found: ${barrierId}`)
    if (barrier.state !== "waiting") throw new Error(`Barrier is already ${barrier.state}`)

    if (!barrier.arrivedWorkers.includes(workerId)) {
      barrier.arrivedWorkers.push(workerId)
    }

    const allArrived = barrier.requiredWorkers.every((w) => barrier.arrivedWorkers.includes(w))
    if (allArrived) {
      barrier.state = "released"
      barrier.releasedAt = new Date().toISOString()
    }

    barriers.set(barrierId, barrier)
    return barrier
  },

  async waitForDependencies(barrierId: string, timeoutMs: number = 30000): Promise<SynchronizationBarrier> {
    const barrier = barriers.get(barrierId)
    if (!barrier) throw new Error(`Barrier not found: ${barrierId}`)
    if (barrier.state === "waiting") {
      const elapsed = Date.now() - new Date(barrier.createdAt).getTime()
      if (elapsed >= timeoutMs) {
        barrier.state = "timed_out"
        barriers.set(barrierId, barrier)
      }
    }
    return barrier
  },

  async releaseBarrier(barrierId: string): Promise<SynchronizationBarrier> {
    const barrier = barriers.get(barrierId)
    if (!barrier) throw new Error(`Barrier not found: ${barrierId}`)
    barrier.state = "released"
    barrier.releasedAt = new Date().toISOString()
    barriers.set(barrierId, barrier)
    return barrier
  },

  async getBarrier(id: string): Promise<SynchronizationBarrier | null> {
    return barriers.get(id) ?? null
  },

  async listBarriers(sessionId?: string): Promise<SynchronizationBarrier[]> {
    let result = Array.from(barriers.values())
    if (sessionId) result = result.filter((b) => b.sessionId === sessionId)
    return result
  },
}
