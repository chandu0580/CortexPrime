import type { DistributedTask, WorkerAssignment, DistributionStrategy } from "./types"
import { generateId } from "@/worker-framework/shared"

interface AvailableWorker {
  id: string
  name: string
  type: string
  capabilities: string[]
  capacity: number
  currentLoad: number
}

const availableWorkers = new Map<string, AvailableWorker>()
const assignments = new Map<string, WorkerAssignment>()

export const TaskDistributionEngine = {
  async registerWorker(id: string, name: string, type: string, capabilities: string[], capacity: number = 5): Promise<void> {
    availableWorkers.set(id, { id, name, type, capabilities, capacity, currentLoad: 0 })
  },

  async unregisterWorker(workerId: string): Promise<void> {
    availableWorkers.delete(workerId)
  },

  async getWorker(workerId: string): Promise<AvailableWorker | null> {
    return availableWorkers.get(workerId) ?? null
  },

  async getAvailableWorkers(type?: string): Promise<AvailableWorker[]> {
    return Array.from(availableWorkers.values()).filter((w) => {
      if (type && w.type !== type) return false
      return w.currentLoad < w.capacity
    })
  },

  async distributeTasks(tasks: DistributedTask[], strategy: DistributionStrategy): Promise<WorkerAssignment[]> {
    const workers = Array.from(availableWorkers.values()).filter((w) => w.currentLoad < w.capacity)
    if (workers.length === 0) throw new Error("No available workers for task distribution")

    const assignments: WorkerAssignment[] = []

    for (const task of tasks) {
      const worker = this.selectWorker(task, workers, strategy)
      if (!worker) continue

      const assignment: WorkerAssignment = {
        id: generateId("exec-assignment"),
        taskId: task.id,
        sessionId: "",
        workerId: worker.id,
        workerType: worker.type,
        status: "assigned",
        assignedAt: new Date().toISOString(),
        completedAt: null,
      }
      assignments.push(assignment)
      task.assignedWorkerId = worker.id
      task.status = "assigned"
      worker.currentLoad++
    }

    return assignments
  },

  async balanceAssignments(tasks: DistributedTask[]): Promise<WorkerAssignment[]> {
    return this.distributeTasks(tasks, "balanced")
  },

  async reserveWorkers(workerIds: string[]): Promise<void> {
    for (const id of workerIds) {
      const worker = availableWorkers.get(id)
      if (worker) worker.currentLoad++
    }
  },

  async releaseAssignments(sessionId: string): Promise<void> {
    const sessionAssignments = Array.from(assignments.values()).filter((a) => a.sessionId === sessionId)
    for (const assignment of sessionAssignments) {
      const worker = availableWorkers.get(assignment.workerId)
      if (worker) worker.currentLoad = Math.max(0, worker.currentLoad - 1)
      assignments.delete(assignment.id)
    }
  },

  async completeAssignment(assignmentId: string): Promise<void> {
    const assignment = assignments.get(assignmentId)
    if (!assignment) throw new Error(`Assignment ${assignmentId} not found`)

    assignment.status = "completed"
    assignment.completedAt = new Date().toISOString()

    const worker = availableWorkers.get(assignment.workerId)
    if (worker) worker.currentLoad = Math.max(0, worker.currentLoad - 1)
  },

  async failAssignment(assignmentId: string): Promise<void> {
    const assignment = assignments.get(assignmentId)
    if (!assignment) throw new Error(`Assignment ${assignmentId} not found`)

    assignment.status = "failed"
    assignment.completedAt = new Date().toISOString()

    const worker = availableWorkers.get(assignment.workerId)
    if (worker) worker.currentLoad = Math.max(0, worker.currentLoad - 1)
  },

  async getAssignmentsBySession(sessionId: string): Promise<WorkerAssignment[]> {
    return Array.from(assignments.values()).filter((a) => a.sessionId === sessionId)
  },

  selectWorker(task: DistributedTask, workers: AvailableWorker[], strategy: DistributionStrategy): AvailableWorker | null {
    const candidates = workers.filter((w) =>
      task.requiredCapabilities.every((c) => w.capabilities.includes(c)),
    )
    if (candidates.length === 0) return null

    switch (strategy) {
      case "balanced":
        return candidates.reduce((a, b) => a.currentLoad <= b.currentLoad ? a : b)
      case "sequential":
        return candidates[0]
      case "parallel":
        return candidates.reduce((a, b) => a.currentLoad <= b.currentLoad ? a : b)
      case "round_robin":
        return candidates[Math.floor(Math.random() * candidates.length)]
      case "capacity_first":
        return candidates.reduce((a, b) => a.capacity - a.currentLoad >= b.capacity - b.currentLoad ? a : b)
      default:
        return candidates[0]
    }
  },

  async getUtilization(): Promise<Record<string, number>> {
    const util: Record<string, number> = {}
    for (const [id, worker] of availableWorkers) {
      util[id] = worker.currentLoad
    }
    return util
  },
}
