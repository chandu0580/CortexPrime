import type { WorkerHeartbeat, WorkerState } from "./types"

const heartbeats = new Map<string, WorkerHeartbeat[]>()

export const WorkerHeartbeatManager = {
  async record(
    workerId: string,
    status: WorkerState,
    currentTaskId: string | null,
    memoryUsage: number = 0,
    cpuUsage: number = 0,
  ): Promise<WorkerHeartbeat> {
    const hb: WorkerHeartbeat = {
      workerId,
      timestamp: new Date().toISOString(),
      status,
      currentTaskId,
      memoryUsage,
      cpuUsage,
      healthy: status === "RUNNING" || status === "READY",
    }

    const existing = heartbeats.get(workerId) ?? []
    heartbeats.set(workerId, [...existing, hb])
    return hb
  },

  async getLatest(workerId: string): Promise<WorkerHeartbeat | null> {
    const hbs = heartbeats.get(workerId)
    if (!hbs || hbs.length === 0) return null
    return hbs[hbs.length - 1]
  },

  async getHistory(workerId: string): Promise<WorkerHeartbeat[]> {
    return heartbeats.get(workerId) ?? []
  },

  async isAlive(workerId: string, thresholdMs: number = 30000): Promise<boolean> {
    const latest = await WorkerHeartbeatManager.getLatest(workerId)
    if (!latest) return false
    return Date.now() - new Date(latest.timestamp).getTime() < thresholdMs
  },

  async getHeartbeatCount(workerId: string): Promise<number> {
    return (heartbeats.get(workerId) ?? []).length
  },

  async getTotalHeartbeats(): Promise<number> {
    let total = 0
    for (const hbs of heartbeats.values()) {
      total += hbs.length
    }
    return total
  },
}
