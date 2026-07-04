import type { ExecutionWorker, WorkerRegistration, WorkerStatus, WorkerCapability } from "./types"
import { generateId } from "./shared"

const workers = new Map<string, WorkerRegistration>()

export const WorkerRegistry = {
  async registerWorker(
    name: string,
    version: string,
    capability: WorkerCapability,
    metadata: Record<string, string> = {},
  ): Promise<ExecutionWorker> {
    const worker: ExecutionWorker = {
      id: generateId("worker"),
      name,
      version,
      capability,
      status: "idle",
      currentSessionId: null,
      currentTaskId: null,
      registeredAt: new Date().toISOString(),
      lastHeartbeat: null,
      totalTasksCompleted: 0,
      totalTasksFailed: 0,
      metadata,
    }

    const registration: WorkerRegistration = {
      worker,
      registeredAt: new Date().toISOString(),
      healthy: true,
      lastCheckedAt: new Date().toISOString(),
    }

    workers.set(worker.id, registration)
    return worker
  },

  async getWorker(workerId: string): Promise<ExecutionWorker | null> {
    return workers.get(workerId)?.worker ?? null
  },

  async getRegistration(workerId: string): Promise<WorkerRegistration | null> {
    return workers.get(workerId) ?? null
  },

  async updateWorkerStatus(workerId: string, status: WorkerStatus): Promise<ExecutionWorker> {
    const reg = workers.get(workerId)
    if (!reg) throw new Error(`Worker not found: ${workerId}`)
    const updated: ExecutionWorker = { ...reg.worker, status }
    workers.set(workerId, { ...reg, worker: updated, lastCheckedAt: new Date().toISOString() })
    return updated
  },

  async assignWorkerToSession(workerId: string, sessionId: string, taskId: string): Promise<ExecutionWorker> {
    const reg = workers.get(workerId)
    if (!reg) throw new Error(`Worker not found: ${workerId}`)
    const updated: ExecutionWorker = {
      ...reg.worker,
      status: "busy",
      currentSessionId: sessionId,
      currentTaskId: taskId,
    }
    workers.set(workerId, { ...reg, worker: updated })
    return updated
  },

  async releaseWorker(workerId: string, taskCompleted: boolean): Promise<ExecutionWorker> {
    const reg = workers.get(workerId)
    if (!reg) throw new Error(`Worker not found: ${workerId}`)
    const updated: ExecutionWorker = {
      ...reg.worker,
      status: "idle",
      currentSessionId: null,
      currentTaskId: null,
      totalTasksCompleted: reg.worker.totalTasksCompleted + (taskCompleted ? 1 : 0),
      totalTasksFailed: reg.worker.totalTasksFailed + (taskCompleted ? 0 : 1),
    }
    workers.set(workerId, { ...reg, worker: updated })
    return updated
  },

  async recordHeartbeat(workerId: string): Promise<void> {
    const reg = workers.get(workerId)
    if (reg) {
      workers.set(workerId, {
        ...reg,
        worker: { ...reg.worker, lastHeartbeat: new Date().toISOString() },
        healthy: true,
        lastCheckedAt: new Date().toISOString(),
      })
    }
  },

  async findAvailableWorker(capability: WorkerCapability): Promise<ExecutionWorker | null> {
    const available = Array.from(workers.values()).filter(
      (r) => r.worker.capability === capability && r.worker.status === "idle" && r.healthy,
    )
    return available.length > 0 ? available[0].worker : null
  },

  async findWorkersByCapability(capability: WorkerCapability): Promise<ExecutionWorker[]> {
    return Array.from(workers.values())
      .filter((r) => r.worker.capability === capability)
      .map((r) => r.worker)
  },

  async getWorkerCounts(): Promise<{ total: number; idle: number; busy: number; error: number; offline: number }> {
    const all = Array.from(workers.values()).map((r) => r.worker)
    return {
      total: all.length,
      idle: all.filter((w) => w.status === "idle").length,
      busy: all.filter((w) => w.status === "busy").length,
      error: all.filter((w) => w.status === "error").length,
      offline: all.filter((w) => w.status === "offline").length,
    }
  },
}
