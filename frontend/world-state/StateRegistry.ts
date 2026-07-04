import type { StateRegistryEntry, StateStatus, StateScope } from "./types"
import { generateId } from "@/worker-framework/shared"

const registry = new Map<string, StateRegistryEntry>()

export const StateRegistry = {
  async register(
    key: string,
    type: string,
    domain: string,
    scope: StateScope = "global",
    schema?: Record<string, unknown>,
  ): Promise<StateRegistryEntry> {
    if (registry.has(key)) throw new Error(`State registry entry ${key} already exists`)

    const entry: StateRegistryEntry = {
      id: generateId("state-reg"),
      key,
      type,
      domain,
      scope,
      status: "active",
      schema: schema ?? {},
      registeredAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }
    registry.set(key, entry)
    return { ...entry }
  },

  async unregister(key: string): Promise<void> {
    if (!registry.has(key)) throw new Error(`State registry entry ${key} not found`)
    registry.delete(key)
  },

  async lookup(key: string): Promise<StateRegistryEntry | null> {
    const entry = registry.get(key)
    return entry ? { ...entry } : null
  },

  async queryByScope(scope: StateScope): Promise<StateRegistryEntry[]> {
    return Array.from(registry.values())
      .filter((e) => e.scope === scope && e.status === "active")
      .map((e) => ({ ...e }))
  },

  async queryByType(type: string): Promise<StateRegistryEntry[]> {
    return Array.from(registry.values())
      .filter((e) => e.type === type && e.status === "active")
      .map((e) => ({ ...e }))
  },

  async queryByDomain(domain: string): Promise<StateRegistryEntry[]> {
    return Array.from(registry.values())
      .filter((e) => e.domain === domain && e.status === "active")
      .map((e) => ({ ...e }))
  },

  async markStatus(key: string, status: StateStatus): Promise<void> {
    const entry = registry.get(key)
    if (!entry) throw new Error(`State registry entry ${key} not found`)
    entry.status = status
    entry.updatedAt = new Date().toISOString()
  },

  async exists(key: string): Promise<boolean> {
    return registry.has(key)
  },

  async listAll(): Promise<StateRegistryEntry[]> {
    return Array.from(registry.values()).map((e) => ({ ...e }))
  },

  async count(): Promise<number> {
    return registry.size
  },

  async getRegisteredTypes(): Promise<string[]> {
    const types = new Set(Array.from(registry.values()).map((e) => e.type))
    return Array.from(types)
  },

  async clear(): Promise<void> {
    registry.clear()
  },
}
