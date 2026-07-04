import type { WorkerAssignment, AssignmentStrategy } from "./types"
import { generateId } from "@/worker-framework/shared"

const assignments = new Map<string, WorkerAssignment>()
let roundRobinIndex = 0

export const WorkerAssignmentEngine = {
  async assignWorker(
    sessionId: string, workerId: string, workerType: string,
    taskId: string, task: string, capabilities: string[],
    strategy: AssignmentStrategy = "least_loaded",
  ): Promise<WorkerAssignment> {
    const assignment: WorkerAssignment = {
      id: generateId("wo-assignment"),
      sessionId,
      workerId,
      workerType,
      taskId,
      task,
      capabilities,
      strategy,
      status: "assigned",
      assignedAt: new Date().toISOString(),
      completedAt: null,
    }
    assignments.set(assignment.id, assignment)
    return assignment
  },

  async getAssignment(assignmentId: string): Promise<WorkerAssignment | null> {
    return assignments.get(assignmentId) ?? null
  },

  async getAssignmentsBySession(sessionId: string): Promise<WorkerAssignment[]> {
    return Array.from(assignments.values()).filter((a) => a.sessionId === sessionId)
  },

  async getAssignmentsByWorker(workerId: string): Promise<WorkerAssignment[]> {
    return Array.from(assignments.values()).filter((a) => a.workerId === workerId)
  },

  async rebalanceAssignments(sessionId: string, workerIds: string[]): Promise<WorkerAssignment[]> {
    const sessionAssignments = await this.getAssignmentsBySession(sessionId)
    const pending = sessionAssignments.filter((a) => a.status === "assigned" || a.status === "pending")

    const rebalanced: WorkerAssignment[] = []
    for (let i = 0; i < pending.length; i++) {
      const workerId = workerIds[i % workerIds.length]
      pending[i].workerId = workerId
      pending[i].assignedAt = new Date().toISOString()
      rebalanced.push(pending[i])
    }
    return rebalanced
  },

  async reserveWorker(workerId: string): Promise<void> {
    const workerAssignments = await this.getAssignmentsByWorker(workerId)
    const active = workerAssignments.filter((a) => a.status === "assigned" || a.status === "active")
    if (active.length > 0) {
      for (const a of active) {
        a.status = "assigned"
      }
    }
  },

  async releaseWorker(assignmentId: string): Promise<WorkerAssignment> {
    const assignment = assignments.get(assignmentId)
    if (!assignment) throw new Error(`Assignment ${assignmentId} not found`)
    assignment.status = "released"
    assignment.completedAt = new Date().toISOString()
    return assignment
  },

  async completeAssignment(assignmentId: string): Promise<WorkerAssignment> {
    const assignment = assignments.get(assignmentId)
    if (!assignment) throw new Error(`Assignment ${assignmentId} not found`)
    assignment.status = "completed"
    assignment.completedAt = new Date().toISOString()
    return assignment
  },

  async failAssignment(assignmentId: string): Promise<WorkerAssignment> {
    const assignment = assignments.get(assignmentId)
    if (!assignment) throw new Error(`Assignment ${assignmentId} not found`)
    assignment.status = "failed"
    assignment.completedAt = new Date().toISOString()
    return assignment
  },

  selectWorker(workerIds: string[], strategy: AssignmentStrategy): string {
    if (workerIds.length === 0) throw new Error("No workers available")

    switch (strategy) {
      case "round_robin": {
        const index = roundRobinIndex % workerIds.length
        roundRobinIndex++
        return workerIds[index]
      }
      case "least_loaded": {
        const loadCounts = new Map<string, number>()
        for (const wid of workerIds) {
          loadCounts.set(wid, Array.from(assignments.values()).filter((a) => a.workerId === wid && a.status === "active").length)
        }
        return [...loadCounts.entries()].reduce((a, b) => a[1] <= b[1] ? a : b)[0]
      }
      case "capability_match":
      case "dedicated":
        return workerIds[0]
      default:
        return workerIds[0]
    }
  },

  async clearSession(sessionId: string): Promise<void> {
    for (const [id, a] of assignments.entries()) {
      if (a.sessionId === sessionId) assignments.delete(id)
    }
  },
}
