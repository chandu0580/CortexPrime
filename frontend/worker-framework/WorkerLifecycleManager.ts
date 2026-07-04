import type { WorkerState, WorkerLifecycle } from "./types"

const transitions: Record<WorkerState, WorkerState[]> = {
  CREATED: ["REGISTERED"],
  REGISTERED: ["INITIALIZED", "SHUTDOWN"],
  INITIALIZED: ["READY", "SHUTDOWN"],
  READY: ["RUNNING", "STOPPED", "SHUTDOWN"],
  RUNNING: ["PAUSED", "STOPPED", "SHUTDOWN"],
  PAUSED: ["READY", "RUNNING", "STOPPED", "SHUTDOWN"],
  STOPPED: ["READY", "SHUTDOWN"],
  SHUTDOWN: [],
}

export const WorkerLifecycleManager = {
  async canTransition(from: WorkerState, to: WorkerState): Promise<boolean> {
    return transitions[from]?.includes(to) ?? false
  },

  async transition(current: WorkerState, target: WorkerState): Promise<WorkerLifecycle> {
    const allowed = transitions[current]
    if (!allowed?.includes(target)) {
      throw new Error(`Invalid worker state transition: ${current} → ${target}`)
    }
    return {
      state: target,
      previousState: current,
      transitions: [current, target],
      startedAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      completedAt: target === "SHUTDOWN" ? new Date().toISOString() : null,
    }
  },

  async getValidTransitions(state: WorkerState): Promise<WorkerState[]> {
    return transitions[state] ?? []
  },

  async isActive(state: WorkerState): Promise<boolean> {
    return state === "READY" || state === "RUNNING" || state === "PAUSED"
  },

  async isTerminal(state: WorkerState): Promise<boolean> {
    return state === "SHUTDOWN"
  },
}
