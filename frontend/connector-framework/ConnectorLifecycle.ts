import type { ConnectorState, ConnectorLifecycle } from "./types"
import { generateId } from "./shared"

const allowedTransitions: Record<ConnectorState, ConnectorState[]> = {
  initialized: ["active", "deactivated", "failed"],
  active: ["paused", "deactivated", "failed"],
  paused: ["active", "deactivated", "failed"],
  failed: ["initialized", "deactivated"],
  deactivated: [],
}

export const ConnectorLifecycleManager = {
  async validateTransition(from: ConnectorState, to: ConnectorState): Promise<boolean> {
    return allowedTransitions[from]?.includes(to) ?? false
  },

  async initialize(state: ConnectorState): Promise<ConnectorLifecycle | null> {
    if (state !== "initialized") return null
    return {
      id: generateId("lifecycle"),
      connectorId: "",
      fromState: state,
      toState: "initialized",
      reason: "connector initialized",
      timestamp: new Date().toISOString(),
    }
  },

  async activate(connectorId: string, state: ConnectorState): Promise<ConnectorLifecycle | null> {
    const allowed = allowedTransitions[state]
    if (!allowed?.includes("active")) return null
    return {
      id: generateId("lifecycle"),
      connectorId,
      fromState: state,
      toState: "active",
      reason: "connector activated",
      timestamp: new Date().toISOString(),
    }
  },

  async pause(connectorId: string, state: ConnectorState): Promise<ConnectorLifecycle | null> {
    const allowed = allowedTransitions[state]
    if (!allowed?.includes("paused")) return null
    return {
      id: generateId("lifecycle"),
      connectorId,
      fromState: state,
      toState: "paused",
      reason: "connector paused",
      timestamp: new Date().toISOString(),
    }
  },

  async resume(connectorId: string, state: ConnectorState): Promise<ConnectorLifecycle | null> {
    const allowed = allowedTransitions[state]
    if (!allowed?.includes("active")) return null
    return {
      id: generateId("lifecycle"),
      connectorId,
      fromState: state,
      toState: "active",
      reason: "connector resumed",
      timestamp: new Date().toISOString(),
    }
  },

  async deactivate(connectorId: string, state: ConnectorState): Promise<ConnectorLifecycle | null> {
    const allowed = allowedTransitions[state]
    if (!allowed?.includes("deactivated")) return null
    return {
      id: generateId("lifecycle"),
      connectorId,
      fromState: state,
      toState: "deactivated",
      reason: "connector deactivated",
      timestamp: new Date().toISOString(),
    }
  },

  async shutdown(connectorId: string, state: ConnectorState): Promise<ConnectorLifecycle | null> {
    if (state === "deactivated") return null
    return {
      id: generateId("lifecycle"),
      connectorId,
      fromState: state,
      toState: "deactivated",
      reason: "connector shutdown",
      timestamp: new Date().toISOString(),
    }
  },

  async getValidTransitions(state: ConnectorState): Promise<ConnectorState[]> {
    return allowedTransitions[state] ?? []
  },

  async isActive(state: ConnectorState): Promise<boolean> {
    return state === "active" || state === "paused"
  },

  async isTerminal(state: ConnectorState): Promise<boolean> {
    return state === "deactivated"
  },
}
