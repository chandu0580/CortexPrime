import type { WorkerExecution, WorkerLifecycleState } from "./types"
import { generateId } from "@/worker-framework/shared"

interface RegisteredWorker {
  id: string
  name: string
  type: string
  capabilities: string[]
  status: WorkerLifecycleState
  registeredAt: string
}

const registeredWorkers = new Map<string, RegisteredWorker>()
const executions = new Map<string, WorkerExecution>()

export const WorkerCoordinator = {
  async registerWorker(id: string, name: string, type: string, capabilities: string[]): Promise<RegisteredWorker> {
    const worker: RegisteredWorker = {
      id,
      name,
      type,
      capabilities,
      status: "registered",
      registeredAt: new Date().toISOString(),
    }
    registeredWorkers.set(id, worker)
    return worker
  },

  async unregisterWorker(workerId: string): Promise<void> {
    registeredWorkers.delete(workerId)
  },

  async getWorker(workerId: string): Promise<RegisteredWorker | null> {
    return registeredWorkers.get(workerId) ?? null
  },

  async getAllWorkers(): Promise<RegisteredWorker[]> {
    return Array.from(registeredWorkers.values())
  },

  async discoverWorkers(type?: string, capabilities?: string[]): Promise<RegisteredWorker[]> {
    return Array.from(registeredWorkers.values()).filter((w) => {
      if (type && w.type !== type) return false
      if (capabilities && !capabilities.every((c) => w.capabilities.includes(c))) return false
      return true
    })
  },

  async coordinateExecution(sessionId: string, workerId: string, taskId: string): Promise<WorkerExecution> {
    const worker = await this.getWorker(workerId)
    if (!worker) throw new Error(`Worker ${workerId} not registered`)

    const execution: WorkerExecution = {
      id: generateId("wo-execution"),
      sessionId,
      workerId,
      workerType: worker.type,
      taskId,
      status: "ready",
      lifecycleState: "starting",
      startedAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      completedAt: null,
      error: null,
    }
    executions.set(execution.id, execution)
    worker.status = "starting"
    return execution
  },

  async coordinateCompletion(executionId: string, error?: string | null): Promise<WorkerExecution> {
    const execution = executions.get(executionId)
    if (!execution) throw new Error(`WorkerExecution ${executionId} not found`)

    const now = new Date().toISOString()
    execution.status = error ? "failed" : "completed"
    execution.lifecycleState = error ? "failed" : "stopped"
    execution.completedAt = now
    execution.error = error ?? null

    const worker = registeredWorkers.get(execution.workerId)
    if (worker) worker.status = error ? "failed" : "stopped"

    return execution
  },

  async getExecution(executionId: string): Promise<WorkerExecution | null> {
    return executions.get(executionId) ?? null
  },

  async getExecutionsBySession(sessionId: string): Promise<WorkerExecution[]> {
    return Array.from(executions.values()).filter((e) => e.sessionId === sessionId)
  },

  async updateExecution(executionId: string, updates: Partial<WorkerExecution>): Promise<WorkerExecution> {
    const execution = executions.get(executionId)
    if (!execution) throw new Error(`WorkerExecution ${executionId} not found`)
    const updated: WorkerExecution = { ...execution, ...updates, updatedAt: new Date().toISOString() }
    executions.set(executionId, updated)
    return updated
  },

  async getWorkerCount(): Promise<number> {
    return registeredWorkers.size
  },
}
