import type { ExecutionTask, TaskState } from "./types"

const transitions: Record<TaskState, TaskState[]> = {
  CREATED: ["QUEUED"],
  QUEUED: ["READY", "CANCELLED"],
  READY: ["ASSIGNED", "CANCELLED"],
  ASSIGNED: ["RUNNING", "FAILED", "CANCELLED"],
  RUNNING: ["WAITING", "COMPLETED", "FAILED", "CANCELLED"],
  WAITING: ["READY", "CANCELLED"],
  COMPLETED: [],
  FAILED: [],
  CANCELLED: [],
}

export const TaskLifecycle = {
  async canTransition(from: TaskState, to: TaskState): Promise<boolean> {
    return transitions[from]?.includes(to) ?? false
  },

  async transition(task: ExecutionTask, targetState: TaskState): Promise<ExecutionTask> {
    const allowed = transitions[task.state]
    if (!allowed?.includes(targetState)) {
      throw new Error(`Invalid task state transition: ${task.state} → ${targetState}`)
    }

    const now = new Date().toISOString()
    const startedAt = targetState === "RUNNING" ? (task.startedAt ?? now) : task.startedAt
    const completedAt = targetState === "COMPLETED" || targetState === "FAILED" || targetState === "CANCELLED"
      ? now
      : task.completedAt

    return {
      ...task,
      state: targetState,
      startedAt,
      completedAt,
    }
  },

  async getValidTransitions(state: TaskState): Promise<TaskState[]> {
    return transitions[state] ?? []
  },

  async isActiveState(state: TaskState): Promise<boolean> {
    return ["QUEUED", "READY", "ASSIGNED", "RUNNING", "WAITING"].includes(state)
  },

  async isTerminalState(state: TaskState): Promise<boolean> {
    return ["COMPLETED", "FAILED", "CANCELLED"].includes(state)
  },

  async canCancel(state: TaskState): Promise<boolean> {
    return transitions[state]?.includes("CANCELLED") ?? false
  },
}
