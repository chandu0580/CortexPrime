import { BootstrapState, type BootstrapTransition } from "./types"
import { generateId } from "./shared"

const allowedTransitions: Record<BootstrapState, BootstrapState[]> = {
  [BootstrapState.PENDING]: [BootstrapState.INITIALIZING, BootstrapState.SHUTDOWN, BootstrapState.FAILED],
  [BootstrapState.INITIALIZING]: [BootstrapState.BOOTSTRAPPING, BootstrapState.SHUTDOWN, BootstrapState.FAILED],
  [BootstrapState.BOOTSTRAPPING]: [BootstrapState.ACTIVE, BootstrapState.SHUTDOWN, BootstrapState.FAILED],
  [BootstrapState.ACTIVE]: [BootstrapState.SHUTDOWN, BootstrapState.FAILED],
  [BootstrapState.SHUTDOWN]: [],
  [BootstrapState.FAILED]: [BootstrapState.PENDING, BootstrapState.SHUTDOWN],
}

const transitions = new Map<string, BootstrapTransition>()

export const BootstrapLifecycle = {
  async validateTransition(from: BootstrapState, to: BootstrapState): Promise<boolean> {
    return allowedTransitions[from]?.includes(to) ?? false
  },

  async record(from: BootstrapState, to: BootstrapState, reason: string): Promise<BootstrapTransition> {
    const transition: BootstrapTransition = {
      id: generateId("btrans"),
      sessionId: "bootstrap",
      fromState: from,
      toState: to,
      reason,
      timestamp: new Date().toISOString(),
    }
    transitions.set(transition.id, transition)
    return transition
  },

  async initialize(from: BootstrapState): Promise<BootstrapTransition | null> {
    if (!(await this.validateTransition(from, BootstrapState.INITIALIZING))) return null
    return this.record(from, BootstrapState.INITIALIZING, "bootstrap initializing")
  },

  async bootstrap(from: BootstrapState): Promise<BootstrapTransition | null> {
    if (!(await this.validateTransition(from, BootstrapState.BOOTSTRAPPING))) return null
    return this.record(from, BootstrapState.BOOTSTRAPPING, "bootstrapping modules")
  },

  async activate(from: BootstrapState): Promise<BootstrapTransition | null> {
    if (!(await this.validateTransition(from, BootstrapState.ACTIVE))) return null
    return this.record(from, BootstrapState.ACTIVE, "bootstrap active")
  },

  async shutdown(from: BootstrapState): Promise<BootstrapTransition | null> {
    if (!(await this.validateTransition(from, BootstrapState.SHUTDOWN))) return null
    return this.record(from, BootstrapState.SHUTDOWN, "bootstrap shutdown")
  },

  async restart(from: BootstrapState): Promise<BootstrapTransition | null> {
    if (from === BootstrapState.SHUTDOWN || from === BootstrapState.FAILED) {
      return this.record(from, BootstrapState.PENDING, "bootstrap restart requested")
    }
    return null
  },

  async getTransitions(): Promise<BootstrapTransition[]> {
    return Array.from(transitions.values())
  },
}
