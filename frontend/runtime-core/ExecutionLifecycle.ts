import type { ExecutionState, ExecutionSession } from "./types"
import { generateId } from "./shared"

const transitions: Record<ExecutionState, ExecutionState[]> = {
  CREATED: ["ASSIGNED"],
  ASSIGNED: ["READY"],
  READY: ["RUNNING", "CANCELLED"],
  RUNNING: ["PAUSED", "COMPLETED", "FAILED", "CANCELLED"],
  PAUSED: ["RESUMED", "CANCELLED", "FAILED"],
  RESUMED: ["RUNNING", "PAUSED", "FAILED", "CANCELLED"],
  COMPLETED: [],
  FAILED: [],
  CANCELLED: [],
}

export const ExecutionLifecycle = {
  async canTransition(from: ExecutionState, to: ExecutionState): Promise<boolean> {
    return transitions[from]?.includes(to) ?? false
  },

  async transition(session: ExecutionSession, targetState: ExecutionState): Promise<ExecutionSession> {
    const allowed = transitions[session.state]
    if (!allowed?.includes(targetState)) {
      throw new Error(`Invalid execution state transition: ${session.state} → ${targetState}`)
    }

    const completedAt = targetState === "COMPLETED" || targetState === "FAILED" || targetState === "CANCELLED"
      ? new Date().toISOString()
      : session.completedAt

    return {
      ...session,
      state: targetState,
      completedAt,
      updatedAt: new Date().toISOString(),
    }
  },

  async getValidTransitions(state: ExecutionState): Promise<ExecutionState[]> {
    return transitions[state] ?? []
  },

  async isActiveState(state: ExecutionState): Promise<boolean> {
    return state === "RUNNING" || state === "RESUMED" || state === "PAUSED"
  },

  async isTerminalState(state: ExecutionState): Promise<boolean> {
    return state === "COMPLETED" || state === "FAILED" || state === "CANCELLED"
  },

  async canResume(state: ExecutionState): Promise<boolean> {
    return state === "PAUSED"
  },

  async canCancel(state: ExecutionState): Promise<boolean> {
    return state === "READY" || state === "RUNNING" || state === "PAUSED" || state === "RESUMED"
  },

  async getAllowedTransitionsMap(): Promise<Record<ExecutionState, ExecutionState[]>> {
    return { ...transitions }
  },
}
