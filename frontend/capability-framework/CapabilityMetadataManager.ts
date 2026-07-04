import type { CapabilityMetadata, CapabilityDefinition } from "./types"
import { CapabilityRegistry } from "./CapabilityRegistry"

export const CapabilityMetadataManager = {
  async get(capabilityId: string): Promise<CapabilityMetadata | null> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) return null
    return structuredClone(definition.metadata)
  },

  async update(capabilityId: string, updates: Partial<CapabilityMetadata>): Promise<void> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }
    definition.metadata = { ...definition.metadata, ...updates }
    definition.updatedAt = new Date().toISOString()
  },

  async setDisplayName(capabilityId: string, name: string): Promise<void> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }
    definition.metadata.displayName = name
    definition.descriptor.name = name
    definition.updatedAt = new Date().toISOString()
  },

  async addTag(capabilityId: string, tag: string): Promise<void> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }
    if (!definition.metadata.tags.includes(tag)) {
      definition.metadata.tags.push(tag)
    }
    if (!definition.descriptor.tags.includes(tag)) {
      definition.descriptor.tags.push(tag)
    }
    definition.updatedAt = new Date().toISOString()
  },

  async removeTag(capabilityId: string, tag: string): Promise<void> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }
    definition.metadata.tags = definition.metadata.tags.filter((t) => t !== tag)
    definition.descriptor.tags = definition.descriptor.tags.filter((t) => t !== tag)
    definition.updatedAt = new Date().toISOString()
  },

  async addMaintainer(capabilityId: string, maintainer: string): Promise<void> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }
    if (!definition.metadata.maintainers.includes(maintainer)) {
      definition.metadata.maintainers.push(maintainer)
    }
    definition.updatedAt = new Date().toISOString()
  },

  async removeMaintainer(capabilityId: string, maintainer: string): Promise<void> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }
    definition.metadata.maintainers = definition.metadata.maintainers.filter((m) => m !== maintainer)
    definition.updatedAt = new Date().toISOString()
  },

  async addChangelogEntry(capabilityId: string, entry: string): Promise<void> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }
    definition.metadata.changelog.push(entry)
    definition.updatedAt = new Date().toISOString()
  },

  async getVersionHistory(capabilityId: string): Promise<{ version: string; updatedAt: string }[]> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) return []
    return [{ version: definition.descriptor.version, updatedAt: definition.updatedAt }]
  },
}
