import { CompositionState, CompositionTransition } from "./types"
import { generateId } from "./shared"

const allowedTransitions: Record<CompositionState, CompositionState[]> = {
  initialized: [CompositionState.ACTIVE, CompositionState.FAILED, CompositionState.SHUTDOWN],
  active: [CompositionState.PAUSED, CompositionState.SHUTDOWN, CompositionState.FAILED],
  paused: [CompositionState.ACTIVE, CompositionState.SHUTDOWN, CompositionState.FAILED],
  shutdown: [],
  failed: [CompositionState.INITIALIZED, CompositionState.SHUTDOWN],
}

const transitions = new Map<string, CompositionTransition>()

export const CompositionLifecycle = {
  async validateTransition(from: CompositionState, to: CompositionState): Promise<boolean> {
    const allowed = allowedTransitions[from]
    return allowed?.includes(to) ?? false
  },

  async initialize(state: CompositionState): Promise<CompositionTransition | null> {
    if (state !== CompositionState.INITIALIZED) return null
    return this.recordTransition(CompositionState.INITIALIZED, CompositionState.INITIALIZED, "composition initialized")
  },

  async activate(state: CompositionState): Promise<CompositionTransition | null> {
    if (!(await this.validateTransition(state, CompositionState.ACTIVE))) return null
    return this.recordTransition(state, CompositionState.ACTIVE, "composition activated")
  },

  async pause(state: CompositionState): Promise<CompositionTransition | null> {
    if (!(await this.validateTransition(state, CompositionState.PAUSED))) return null
    return this.recordTransition(state, CompositionState.PAUSED, "composition paused")
  },

  async resume(state: CompositionState): Promise<CompositionTransition | null> {
    if (!(await this.validateTransition(state, CompositionState.ACTIVE))) return null
    return this.recordTransition(state, CompositionState.ACTIVE, "composition resumed")
  },

  async shutdown(state: CompositionState): Promise<CompositionTransition | null> {
    if (!(await this.validateTransition(state, CompositionState.SHUTDOWN))) return null
    return this.recordTransition(state, CompositionState.SHUTDOWN, "composition shutdown")
  },

  async recordTransition(from: CompositionState, to: CompositionState, reason: string): Promise<CompositionTransition> {
    const transition: CompositionTransition = {
      id: generateId("transition"),
      compositionId: "platform",
      fromState: from,
      toState: to,
      reason,
      timestamp: new Date().toISOString(),
    }
    transitions.set(transition.id, transition)
    return transition
  },

  async getTransitions(): Promise<CompositionTransition[]> {
    return Array.from(transitions.values())
  },

  async getValidTransitions(state: CompositionState): Promise<CompositionState[]> {
    return allowedTransitions[state] ?? []
  },
}
