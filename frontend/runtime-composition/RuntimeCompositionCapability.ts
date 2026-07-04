import type { RuntimeCapabilityDefinition } from "./types"

export const RuntimeCompositionCapabilityDefinitions: RuntimeCapabilityDefinition[] = [
  { id: "runtime-composition",   name: "runtime.composition",   description: "Compose runtime subsystems",              version: "1.0.0", enabled: true },
  { id: "runtime-lifecycle",     name: "runtime.lifecycle",     description: "Manage runtime lifecycle transitions",     version: "1.0.0", enabled: true },
  { id: "runtime-dependencies",  name: "runtime.dependencies",  description: "Resolve runtime module dependencies",      version: "1.0.0", enabled: true },
  { id: "runtime-validation",    name: "runtime.validation",    description: "Validate runtime composition integrity",   version: "1.0.0", enabled: true },
  { id: "runtime-health",        name: "runtime.health",        description: "Monitor runtime health",                  version: "1.0.0", enabled: true },
  { id: "runtime-metrics",       name: "runtime.metrics",       description: "Collect runtime metrics",                 version: "1.0.0", enabled: true },
]

export const RuntimeCompositionCapability = {
  async getDefinitions(): Promise<RuntimeCapabilityDefinition[]> {
    return [...RuntimeCompositionCapabilityDefinitions]
  },
  async getDefinition(name: string): Promise<RuntimeCapabilityDefinition | undefined> {
    return RuntimeCompositionCapabilityDefinitions.find((d) => d.name === name)
  },
}
