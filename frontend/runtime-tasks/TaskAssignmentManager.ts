import type { TaskAssignment } from "./types"
import { generateId } from "./shared"

const assignments = new Map<string, TaskAssignment>()

export const TaskAssignmentManager = {
  async assign(workerId: string, taskId: string, sessionId: string): Promise<TaskAssignment> {
    const assignment: TaskAssignment = {
      id: generateId("assign"),
      taskId,
      sessionId,
      workerId,
      assignedAt: new Date().toISOString(),
      startedAt: null,
      completedAt: null,
      status: "assigned",
    }
    assignments.set(assignment.id, assignment)
    return assignment
  },

  async markStarted(assignmentId: string): Promise<TaskAssignment> {
    const assignment = assignments.get(assignmentId)
    if (!assignment) throw new Error(`Assignment not found: ${assignmentId}`)
    const updated: TaskAssignment = {
      ...assignment,
      status: "started",
      startedAt: new Date().toISOString(),
    }
    assignments.set(assignmentId, updated)
    return updated
  },

  async markCompleted(assignmentId: string, success: boolean): Promise<TaskAssignment> {
    const assignment = assignments.get(assignmentId)
    if (!assignment) throw new Error(`Assignment not found: ${assignmentId}`)
    const updated: TaskAssignment = {
      ...assignment,
      status: success ? "completed" : "failed",
      completedAt: new Date().toISOString(),
    }
    assignments.set(assignmentId, updated)
    return updated
  },

  async revoke(assignmentId: string): Promise<TaskAssignment> {
    const assignment = assignments.get(assignmentId)
    if (!assignment) throw new Error(`Assignment not found: ${assignmentId}`)
    const updated: TaskAssignment = {
      ...assignment,
      status: "revoked",
      completedAt: new Date().toISOString(),
    }
    assignments.set(assignmentId, updated)
    return updated
  },

  async getAssignment(assignmentId: string): Promise<TaskAssignment | null> {
    return assignments.get(assignmentId) ?? null
  },

  async getTaskAssignment(taskId: string): Promise<TaskAssignment | null> {
    return Array.from(assignments.values()).find((a) => a.taskId === taskId && a.status !== "revoked") ?? null
  },

  async getWorkerAssignments(workerId: string): Promise<TaskAssignment[]> {
    return Array.from(assignments.values()).filter((a) => a.workerId === workerId)
  },

  async getSessionAssignments(sessionId: string): Promise<TaskAssignment[]> {
    return Array.from(assignments.values()).filter((a) => a.sessionId === sessionId)
  },

  async revokeSessionAssignments(sessionId: string): Promise<void> {
    const sessionAssignments = await TaskAssignmentManager.getSessionAssignments(sessionId)
    for (const a of sessionAssignments) {
      if (a.status === "assigned" || a.status === "started") {
        await TaskAssignmentManager.revoke(a.id)
      }
    }
  },

  async getActiveCount(): Promise<number> {
    return Array.from(assignments.values()).filter((a) => a.status === "assigned" || a.status === "started").length
  },
}
