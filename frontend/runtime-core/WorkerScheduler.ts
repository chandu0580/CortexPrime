import type { ExecutionSession, ExecutionWorker, WorkerAssignment, WorkerCapability, ExecutionTask } from "./types"
import { WorkerRegistry } from "./WorkerRegistry"
import { generateId } from "./shared"

const assignments = new Map<string, WorkerAssignment>()

export const WorkerScheduler = {
  async assignWorker(
    session: ExecutionSession,
    capability: WorkerCapability,
    taskId: string,
  ): Promise<{ session: ExecutionSession; worker: ExecutionWorker; assignment: WorkerAssignment }> {
    const worker = await WorkerRegistry.findAvailableWorker(capability)
    if (!worker) throw new Error(`No available worker for capability: ${capability}`)

    const updatedWorker = await WorkerRegistry.assignWorkerToSession(worker.id, session.id, taskId)

    const assignment: WorkerAssignment = {
      id: generateId("assignment"),
      sessionId: session.id,
      workerId: worker.id,
      taskId,
      assignedAt: new Date().toISOString(),
      completedAt: null,
      status: "active",
    }
    assignments.set(assignment.id, assignment)

    const updatedSession: ExecutionSession = {
      ...session,
      state: "ASSIGNED",
      workerId: worker.id,
      worker: updatedWorker,
      assignment,
      updatedAt: new Date().toISOString(),
    }

    return { session: updatedSession, worker: updatedWorker, assignment }
  },

  async releaseWorker(sessionId: string, taskCompleted: boolean): Promise<void> {
    const activeAssignments = Array.from(assignments.values()).filter(
      (a) => a.sessionId === sessionId && a.status === "active",
    )

    for (const assignment of activeAssignments) {
      await WorkerRegistry.releaseWorker(assignment.workerId, taskCompleted)
      assignments.set(assignment.id, {
        ...assignment,
        status: taskCompleted ? "completed" : "failed",
        completedAt: new Date().toISOString(),
      })
    }
  },

  async getAssignment(sessionId: string): Promise<WorkerAssignment | null> {
    return Array.from(assignments.values()).find(
      (a) => a.sessionId === sessionId && a.status === "active",
    ) ?? null
  },

  async getSessionAssignments(sessionId: string): Promise<WorkerAssignment[]> {
    return Array.from(assignments.values()).filter((a) => a.sessionId === sessionId)
  },

  async revokeAssignment(sessionId: string): Promise<void> {
    const activeAssignments = Array.from(assignments.values()).filter(
      (a) => a.sessionId === sessionId && a.status === "active",
    )
    for (const assignment of activeAssignments) {
      await WorkerRegistry.releaseWorker(assignment.workerId, false)
      assignments.set(assignment.id, {
        ...assignment,
        status: "revoked",
        completedAt: new Date().toISOString(),
      })
    }
  },
}
