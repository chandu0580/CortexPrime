import type { WorldState, StateEntry, StateScope } from "./types"
import { generateId } from "@/worker-framework/shared"

let worldState: WorldState | null = null

export const WorldStateManager = {
  async createState(name: string, version: string = "1.0.0"): Promise<WorldState> {
    if (worldState) throw new Error("World state already exists. Use mergeState() to update.")
    worldState = {
      id: generateId("world-state"),
      name,
      version,
      entries: {},
      registeredTypes: [],
      scopes: ["global"],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      entryCount: 0,
    }
    return { ...worldState }
  },

  async getState(): Promise<WorldState | null> {
    return worldState ? { ...worldState, entries: { ...worldState.entries } } : null
  },

  async updateState(key: string, value: unknown, metadata?: Record<string, string>): Promise<StateEntry> {
    if (!worldState) throw new Error("World state not initialized. Call createState() first.")
    const existing = worldState.entries[key]
    const now = new Date().toISOString()

    const entry: StateEntry = existing
      ? { ...existing, value, version: existing.version + 1, updatedAt: now, metadata: { ...existing.metadata, ...metadata } }
      : {
          id: generateId("state-entry"),
          key,
          value,
          type: typeof value,
          status: "active",
          scope: "global",
          domain: "default",
          owner: "system",
          version: 1,
          tags: [],
          metadata: metadata ?? {},
          references: [],
          createdAt: now,
          updatedAt: now,
          expiresAt: null,
        }

    worldState.entries[key] = entry
    worldState.entryCount = Object.keys(worldState.entries).length
    worldState.updatedAt = now
    return { ...entry }
  },

  async removeState(key: string): Promise<void> {
    if (!worldState) throw new Error("World state not initialized.")
    const entry = worldState.entries[key]
    if (!entry) throw new Error(`State entry ${key} not found.`)
    entry.status = "deleted"
    entry.updatedAt = new Date().toISOString()
    worldState.updatedAt = new Date().toISOString()
  },

  async mergeState(partial: Partial<WorldState>): Promise<WorldState> {
    if (!worldState) throw new Error("World state not initialized.")
    if (partial.entries) {
      for (const [key, entry] of Object.entries(partial.entries)) {
        worldState.entries[key] = entry as StateEntry
      }
    }
    if (partial.registeredTypes) worldState.registeredTypes = [...new Set([...worldState.registeredTypes, ...partial.registeredTypes])]
    if (partial.scopes) worldState.scopes = [...new Set([...worldState.scopes, ...partial.scopes])]
    worldState.entryCount = Object.keys(worldState.entries).length
    worldState.updatedAt = new Date().toISOString()
    return { ...worldState, entries: { ...worldState.entries } }
  },

  async getEntry(key: string): Promise<StateEntry | null> {
    if (!worldState) return null
    const entry = worldState.entries[key]
    return entry && entry.status !== "deleted" ? { ...entry } : null
  },

  async queryByScope(scope: StateScope): Promise<StateEntry[]> {
    if (!worldState) return []
    return Object.values(worldState.entries)
      .filter((e) => e.scope === scope && e.status !== "deleted")
      .map((e) => ({ ...e }))
  },

  async queryByDomain(domain: string): Promise<StateEntry[]> {
    if (!worldState) return []
    return Object.values(worldState.entries)
      .filter((e) => e.domain === domain && e.status !== "deleted")
      .map((e) => ({ ...e }))
  },

  async queryByType(type: string): Promise<StateEntry[]> {
    if (!worldState) return []
    return Object.values(worldState.entries)
      .filter((e) => e.type === type && e.status !== "deleted")
      .map((e) => ({ ...e }))
  },

  async getActiveEntries(): Promise<StateEntry[]> {
    if (!worldState) return []
    return Object.values(worldState.entries)
      .filter((e) => e.status === "active")
      .map((e) => ({ ...e }))
  },

  async getAllEntries(): Promise<StateEntry[]> {
    if (!worldState) return []
    return Object.values(worldState.entries).map((e) => ({ ...e }))
  },

  async entryExists(key: string): Promise<boolean> {
    return worldState ? (worldState.entries[key]?.status ?? "deleted") !== "deleted" : false
  },

  async clear(): Promise<void> {
    worldState = null
  },

  async getSnapshotData(): Promise<Record<string, unknown>> {
    if (!worldState) return {}
    const data: Record<string, unknown> = {}
    for (const [key, entry] of Object.entries(worldState.entries)) {
      data[key] = entry.value
    }
    return data
  },

  async restoreFromData(data: Record<string, unknown>): Promise<void> {
    if (!worldState) throw new Error("World state not initialized.")
    const now = new Date().toISOString()
    for (const [key, value] of Object.entries(data)) {
      worldState.entries[key] = {
        id: generateId("state-entry"),
        key,
        value,
        type: typeof value,
        status: "active",
        scope: "global",
        domain: "default",
        owner: "system",
        version: 1,
        tags: [],
        metadata: {},
        references: [],
        createdAt: now,
        updatedAt: now,
        expiresAt: null,
      }
    }
    worldState.entryCount = Object.keys(worldState.entries).length
    worldState.updatedAt = now
  },
}
