import type { ExecutionHeartbeat, ExecutionSession, ExecutionState } from "./types"
import { WorkerRegistry } from "./WorkerRegistry"
import { generateId } from "./shared"

const heartbeats = new Map<string, ExecutionHeartbeat>()
const MISSED_HEARTBEAT_LIMIT = 3
const HEARTBEAT_INTERVAL_MS = 30000

export const HeartbeatManager = {
  async recordHeartbeat(
    workerId: string,
    sessionId: string,
    taskId: string,
    status: "alive" | "degraded" | "stuck" = "alive",
    message: string = "Worker alive",
  ): Promise<ExecutionHeartbeat> {
    const heartbeat: ExecutionHeartbeat = {
      id: generateId("hb"),
      workerId,
      sessionId,
      taskId,
      timestamp: new Date().toISOString(),
      status,
      message,
    }
    heartbeats.set(heartbeat.id, heartbeat)
    await WorkerRegistry.recordHeartbeat(workerId)
    return heartbeat
  },

  async getLatestHeartbeat(workerId: string): Promise<ExecutionHeartbeat | null> {
    const workerHeartbeats = Array.from(heartbeats.values())
      .filter((h) => h.workerId === workerId)
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
    return workerHeartbeats[0] ?? null
  },

  async getSessionHeartbeats(sessionId: string): Promise<ExecutionHeartbeat[]> {
    return Array.from(heartbeats.values())
      .filter((h) => h.sessionId === sessionId)
      .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
  },

  async isWorkerAlive(workerId: string): Promise<boolean> {
    const latest = await HeartbeatManager.getLatestHeartbeat(workerId)
    if (!latest) return false
    const elapsed = Date.now() - new Date(latest.timestamp).getTime()
    return elapsed < MISSED_HEARTBEAT_LIMIT * HEARTBEAT_INTERVAL_MS
  },

  async checkSessionHealth(sessionId: string): Promise<{ healthy: boolean; degraded: boolean; stuck: boolean }> {
    const sessionHeartbeats = await HeartbeatManager.getSessionHeartbeats(sessionId)
    const recent = sessionHeartbeats.slice(-5)
    return {
      healthy: recent.every((h) => h.status === "alive"),
      degraded: recent.some((h) => h.status === "degraded"),
      stuck: recent.some((h) => h.status === "stuck"),
    }
  },

  async getHeartbeatCount(): Promise<number> {
    return heartbeats.size
  },
}
