import type { CompositionCapabilityDefinition } from "./types"

export const PlatformCompositionCapabilityDefinitions: CompositionCapabilityDefinition[] = [
  { id: "platform-composition",   name: "platform.composition",   description: "Compose platform modules",              version: "1.0.0", enabled: true },
  { id: "platform-dependencies",  name: "platform.dependencies",  description: "Resolve module dependencies",           version: "1.0.0", enabled: true },
  { id: "platform-lifecycle",     name: "platform.lifecycle",     description: "Manage composition lifecycle",          version: "1.0.0", enabled: true },
  { id: "platform-validation",    name: "platform.validation",    description: "Validate composition integrity",        version: "1.0.0", enabled: true },
  { id: "platform-health",        name: "platform.health",        description: "Monitor composition health",            version: "1.0.0", enabled: true },
  { id: "platform-metrics",       name: "platform.metrics",       description: "Collect composition metrics",           version: "1.0.0", enabled: true },
]

export const PlatformCompositionCapability = {
  async getDefinitions(): Promise<CompositionCapabilityDefinition[]> {
    return [...PlatformCompositionCapabilityDefinitions]
  },

  async getDefinition(name: string): Promise<CompositionCapabilityDefinition | undefined> {
    return PlatformCompositionCapabilityDefinitions.find((d) => d.name === name)
  },
}