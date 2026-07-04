import type { StateTransition, StateChangeType } from "./types"
import { WorldStateManager } from "./WorldStateManager"
import { generateId } from "@/worker-framework/shared"

const transitions: StateTransition[] = []
const MAX_HISTORY = 1000

export const StateTransitionEngine = {
  async transition(
    entryKey: string,
    to: unknown,
    type: StateChangeType,
    actor: string,
    reason: string,
    metadata?: Record<string, string>,
  ): Promise<StateTransition> {
    const startTime = Date.now()
    const entry = await WorldStateManager.getEntry(entryKey)
    const from = entry?.value ?? null

    if (type === "update" && !entry) {
      throw new Error(`Cannot update non-existent state entry: ${entryKey}`)
    }

    await WorldStateManager.updateState(entryKey, to, metadata)

    const transition: StateTransition = {
      id: generateId("state-transition"),
      entryKey,
      from,
      to,
      type,
      status: "committed",
      actor,
      reason,
      metadata: metadata ?? {},
      timestamp: new Date().toISOString(),
      durationMs: Date.now() - startTime,
    }

    if (transitions.length >= MAX_HISTORY) transitions.shift()
    transitions.push(transition)

    return { ...transition }
  },

  async validateTransition(entryKey: string, to: unknown, type: StateChangeType): Promise<{ valid: boolean; reason: string }> {
    if (type === "create") {
      const exists = await WorldStateManager.entryExists(entryKey)
      if (exists) return { valid: false, reason: `Entry ${entryKey} already exists. Use update instead.` }
      return { valid: true, reason: "Create transition is valid." }
    }

    if (type === "update" || type === "remove") {
      const exists = await WorldStateManager.entryExists(entryKey)
      if (!exists) return { valid: false, reason: `Entry ${entryKey} does not exist.` }
      return { valid: true, reason: "Transition is valid." }
    }

    return { valid: true, reason: "Transition type allows all entries." }
  },

  async rollback(transitionId: string): Promise<StateTransition> {
    const index = transitions.findIndex((t) => t.id === transitionId)
    if (index === -1) throw new Error(`Transition ${transitionId} not found.`)
    const transition = transitions[index]

    if (transition.status !== "committed") {
      throw new Error(`Transition ${transitionId} is not in committed state.`)
    }

    const rollbackType: StateChangeType = transition.type === "create" ? "remove" : "update"
    const isCreate = transition.type === "create"

    if (isCreate) {
      await WorldStateManager.removeState(transition.entryKey)
    } else {
      await WorldStateManager.updateState(transition.entryKey, transition.from)
    }

    transition.status = "rolled_back"

    const rollbackTransition: StateTransition = {
      id: generateId("state-transition"),
      entryKey: transition.entryKey,
      from: transition.to,
      to: transition.from,
      type: rollbackType,
      status: "committed",
      actor: "system",
      reason: `Rollback of transition ${transitionId}`,
      metadata: { rollbackOf: transitionId },
      timestamp: new Date().toISOString(),
      durationMs: 0,
    }

    transitions.push(rollbackTransition)
    return { ...rollbackTransition }
  },

  async history(entryKey?: string): Promise<StateTransition[]> {
    let result = [...transitions]
    if (entryKey) result = result.filter((t) => t.entryKey === entryKey)
    return result.reverse().map((t) => ({ ...t }))
  },

  async getTransition(transitionId: string): Promise<StateTransition | null> {
    const transition = transitions.find((t) => t.id === transitionId)
    return transition ? { ...transition } : null
  },

  async count(): Promise<number> {
    return transitions.length
  },

  async countByEntry(entryKey: string): Promise<number> {
    return transitions.filter((t) => t.entryKey === entryKey).length
  },

  async clear(): Promise<void> {
    transitions.length = 0
  },
}
