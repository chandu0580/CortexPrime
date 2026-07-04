import { RuntimeCompositionState, type RuntimeTransition } from "./types"
import { generateId } from "./shared"

const allowed: Record<RuntimeCompositionState, RuntimeCompositionState[]> = {
  [RuntimeCompositionState.PENDING]: [RuntimeCompositionState.INITIALIZING, RuntimeCompositionState.SHUTDOWN, RuntimeCompositionState.FAILED],
  [RuntimeCompositionState.INITIALIZING]: [RuntimeCompositionState.ACTIVE, RuntimeCompositionState.SHUTDOWN, RuntimeCompositionState.FAILED],
  [RuntimeCompositionState.ACTIVE]: [RuntimeCompositionState.PAUSED, RuntimeCompositionState.SHUTDOWN, RuntimeCompositionState.FAILED],
  [RuntimeCompositionState.PAUSED]: [RuntimeCompositionState.ACTIVE, RuntimeCompositionState.SHUTDOWN, RuntimeCompositionState.FAILED],
  [RuntimeCompositionState.SHUTDOWN]: [],
  [RuntimeCompositionState.FAILED]: [RuntimeCompositionState.PENDING, RuntimeCompositionState.SHUTDOWN],
}

const transitions = new Map<string, RuntimeTransition>()

export const RuntimeLifecycle = {
  async validateTransition(from: RuntimeCompositionState, to: RuntimeCompositionState): Promise<boolean> {
    return allowed[from]?.includes(to) ?? false
  },

  async record(from: RuntimeCompositionState, to: RuntimeCompositionState, reason: string): Promise<RuntimeTransition> {
    const t: RuntimeTransition = {
      id: generateId("rttrans"), compositionId: "runtime",
      fromState: from, toState: to, reason, timestamp: new Date().toISOString(),
    }
    transitions.set(t.id, t)
    return t
  },

  async initialize(from: RuntimeCompositionState): Promise<RuntimeTransition | null> {
    if (!(await this.validateTransition(from, RuntimeCompositionState.INITIALIZING))) return null
    return this.record(from, RuntimeCompositionState.INITIALIZING, "runtime initializing")
  },

  async activate(from: RuntimeCompositionState): Promise<RuntimeTransition | null> {
    if (!(await this.validateTransition(from, RuntimeCompositionState.ACTIVE))) return null
    return this.record(from, RuntimeCompositionState.ACTIVE, "runtime active")
  },

  async pause(from: RuntimeCompositionState): Promise<RuntimeTransition | null> {
    if (!(await this.validateTransition(from, RuntimeCompositionState.PAUSED))) return null
    return this.record(from, RuntimeCompositionState.PAUSED, "runtime paused")
  },

  async resume(from: RuntimeCompositionState): Promise<RuntimeTransition | null> {
    if (!(await this.validateTransition(from, RuntimeCompositionState.ACTIVE))) return null
    return this.record(from, RuntimeCompositionState.ACTIVE, "runtime resumed")
  },

  async shutdown(from: RuntimeCompositionState): Promise<RuntimeTransition | null> {
    if (!(await this.validateTransition(from, RuntimeCompositionState.SHUTDOWN))) return null
    return this.record(from, RuntimeCompositionState.SHUTDOWN, "runtime shutdown")
  },

  async restart(from: RuntimeCompositionState): Promise<RuntimeTransition | null> {
    if (from === RuntimeCompositionState.SHUTDOWN || from === RuntimeCompositionState.FAILED) return this.record(from, RuntimeCompositionState.PENDING, "runtime restart requested")
    return null
  },

  async getTransitions(): Promise<RuntimeTransition[]> {
    return Array.from(transitions.values())
  },
}
