import type { WorkerAssignment, WorkerInvocation, WorkerResult, WorkerRole } from "./types"
import { generateId } from "@/worker-framework/shared"

interface RegisteredWorker {
  id: string
  name: string
  type: string
  roles: WorkerRole[]
  available: boolean
  registeredAt: string
}

const registeredWorkers = new Map<string, RegisteredWorker>()
const assignments = new Map<string, WorkerAssignment>()
const invocations = new Map<string, WorkerInvocation>()

export const WorkerCoordinationEngine = {
  async registerWorker(id: string, name: string, type: string, roles: WorkerRole[]): Promise<RegisteredWorker> {
    const worker: RegisteredWorker = {
      id,
      name,
      type,
      roles,
      available: true,
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

  async getAvailableWorkers(role?: WorkerRole): Promise<RegisteredWorker[]> {
    return Array.from(registeredWorkers.values()).filter((w) => {
      if (!w.available) return false
      if (role) return w.roles.includes(role)
      return true
    })
  },

  async assignWorker(sessionId: string, workerId: string, role: WorkerRole, task: string): Promise<WorkerAssignment> {
    const worker = await this.getWorker(workerId)
    if (!worker) throw new Error(`Worker ${workerId} not registered`)
    if (!worker.available) throw new Error(`Worker ${workerId} is not available`)
    if (!worker.roles.includes(role)) throw new Error(`Worker ${workerId} does not support role ${role}`)

    const assignment: WorkerAssignment = {
      id: generateId("cog-assignment"),
      sessionId,
      workerId,
      workerType: worker.type,
      role,
      status: "assigned",
      task,
      assignedAt: new Date().toISOString(),
      completedAt: null,
      result: null,
    }
    assignments.set(assignment.id, assignment)
    worker.available = false
    return assignment
  },

  async releaseWorker(assignmentId: string): Promise<void> {
    const assignment = assignments.get(assignmentId)
    if (!assignment) throw new Error(`Assignment ${assignmentId} not found`)

    assignment.status = "released"
    assignment.completedAt = new Date().toISOString()

    const worker = registeredWorkers.get(assignment.workerId)
    if (worker) worker.available = true
  },

  async invokeWorker(assignmentId: string, payload: Record<string, unknown>): Promise<WorkerInvocation> {
    const assignment = assignments.get(assignmentId)
    if (!assignment) throw new Error(`Assignment ${assignmentId} not found`)

    const invocation: WorkerInvocation = {
      assignmentId,
      workerId: assignment.workerId,
      sessionId: assignment.sessionId,
      task: assignment.task,
      payload,
      status: "in_progress",
      invokedAt: new Date().toISOString(),
      completedAt: null,
    }
    invocations.set(assignment.id, invocation)
    assignment.status = "active"
    return invocation
  },

  async completeInvocation(assignmentId: string, result: WorkerResult): Promise<void> {
    const invocation = Array.from(invocations.values()).find((i) => i.assignmentId === assignmentId)
    if (!invocation) throw new Error(`Invocation for assignment ${assignmentId} not found`)

    invocation.status = result.success ? "completed" : "failed"
    invocation.completedAt = result.completedAt

    const assignment = assignments.get(assignmentId)
    if (assignment) {
      assignment.status = result.success ? "completed" : "failed"
      assignment.completedAt = result.completedAt
      assignment.result = result
    }
  },

  async broadcast(sessionId: string, task: string, payload: Record<string, unknown>): Promise<WorkerAssignment[]> {
    const workers = Array.from(registeredWorkers.values()).filter((w) => w.available)
    const results: WorkerAssignment[] = []

    for (const worker of workers) {
      const assignment = await this.assignWorker(sessionId, worker.id, worker.roles[0], task)
      await this.invokeWorker(assignment.id, payload)
      results.push(assignment)
    }
    return results
  },

  async collectResults(sessionId: string): Promise<WorkerResult[]> {
    return Array.from(assignments.values())
      .filter((a) => a.sessionId === sessionId && a.result !== null)
      .map((a) => a.result!)
  },

  async getAssignmentsBySession(sessionId: string): Promise<WorkerAssignment[]> {
    return Array.from(assignments.values()).filter((a) => a.sessionId === sessionId)
  },

  async getAssignment(assignmentId: string): Promise<WorkerAssignment | null> {
    return assignments.get(assignmentId) ?? null
  },

  async getWorkerUtilization(): Promise<Record<string, number>> {
    const util: Record<string, number> = {}
    for (const id of registeredWorkers.keys()) {
      const activeAssignments = Array.from(assignments.values()).filter(
        (a) => a.workerId === id && a.status === "active",
      )
      util[id] = activeAssignments.length
    }
    return util
  },
}
