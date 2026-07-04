import type { CapabilityConfiguration, CapabilityDefinition } from "./types"
import { CapabilityRegistry } from "./CapabilityRegistry"

export const CapabilityConfigurationManager = {
  async load(capabilityId: string): Promise<CapabilityConfiguration> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }
    return structuredClone(definition.configuration)
  },

  async updateSetting(capabilityId: string, key: string, value: unknown): Promise<void> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }
    definition.configuration.settings[key] = value
    definition.updatedAt = new Date().toISOString()
  },

  async updateDefault(capabilityId: string, key: string, value: unknown): Promise<void> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }
    definition.configuration.defaults[key] = value
    definition.updatedAt = new Date().toISOString()
  },

  async setOverride(capabilityId: string, key: string, value: unknown): Promise<void> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }
    definition.configuration.overrides[key] = value
    definition.updatedAt = new Date().toISOString()
  },

  async getSetting(capabilityId: string, key: string): Promise<unknown> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }
    const config = definition.configuration
    return config.overrides[key] ?? config.settings[key] ?? config.defaults[key] ?? null
  },

  async setEnvironment(capabilityId: string, key: string, value: string): Promise<void> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }
    definition.configuration.environment[key] = value
    definition.updatedAt = new Date().toISOString()
  },

  async toggleFeature(capabilityId: string, feature: string, enabled: boolean): Promise<void> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }
    definition.configuration.features[feature] = enabled
    definition.updatedAt = new Date().toISOString()
  },

  async isFeatureEnabled(capabilityId: string, feature: string): Promise<boolean> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }
    return definition.configuration.features[feature] ?? false
  },

  async setTimeout(capabilityId: string, operation: string, ms: number): Promise<void> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }
    definition.configuration.timeouts[operation] = ms
    definition.updatedAt = new Date().toISOString()
  },

  async getTimeout(capabilityId: string, operation: string, defaultMs: number): Promise<number> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }
    return definition.configuration.timeouts[operation] ?? defaultMs
  },

  async setLimit(capabilityId: string, resource: string, limit: number): Promise<void> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }
    definition.configuration.limits[resource] = limit
    definition.updatedAt = new Date().toISOString()
  },

  async getLimit(capabilityId: string, resource: string, defaultLimit: number): Promise<number> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }
    return definition.configuration.limits[resource] ?? defaultLimit
  },

  async reset(capabilityId: string): Promise<void> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }
    definition.configuration = {
      settings: {},
      defaults: {},
      overrides: {},
      environment: {},
      features: {},
      timeouts: {},
      limits: {},
    }
    definition.updatedAt = new Date().toISOString()
  },
}
