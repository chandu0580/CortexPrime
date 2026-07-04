import type { CapabilityDefinition, CapabilityStatus } from "./types"

const registry = new Map<string, CapabilityDefinition>()

export const CapabilityRegistry = {
  async register(definition: CapabilityDefinition): Promise<void> {
    if (registry.has(definition.id)) {
      throw new Error(`Capability ${definition.id} is already registered`)
    }
    registry.set(definition.id, structuredClone(definition))
  },

  async unregister(capabilityId: string): Promise<void> {
    if (!registry.has(capabilityId)) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }
    registry.delete(capabilityId)
  },

  async get(capabilityId: string): Promise<CapabilityDefinition | null> {
    const entry = registry.get(capabilityId)
    return entry ? structuredClone(entry) : null
  },

  async list(): Promise<CapabilityDefinition[]> {
    return Array.from(registry.values()).map((d) => structuredClone(d))
  },

  async findByStatus(status: CapabilityStatus): Promise<CapabilityDefinition[]> {
    return Array.from(registry.values())
      .filter((d) => d.descriptor.status === status)
      .map((d) => structuredClone(d))
  },

  async findByCategory(category: string): Promise<CapabilityDefinition[]> {
    return Array.from(registry.values())
      .filter((d) => d.descriptor.category === category)
      .map((d) => structuredClone(d))
  },

  async findByTag(tag: string): Promise<CapabilityDefinition[]> {
    return Array.from(registry.values())
      .filter((d) => d.descriptor.tags.includes(tag))
      .map((d) => structuredClone(d))
  },

  async findByType(type: string): Promise<CapabilityDefinition[]> {
    return Array.from(registry.values())
      .filter((d) => d.descriptor.type === type)
      .map((d) => structuredClone(d))
  },

  async exists(capabilityId: string): Promise<boolean> {
    return registry.has(capabilityId)
  },

  async count(): Promise<number> {
    return registry.size
  },

  async clear(): Promise<void> {
    registry.clear()
  },
}
