import type { RuntimeCapabilityDefinition } from "./types"

export const CortexRuntimeCapabilityDefinitions: RuntimeCapabilityDefinition[] = [
  { id: "rt-startup",    name: "runtime.startup",    description: "Start up the CortexPrime platform",  version: "1.0.0", enabled: true },
  { id: "rt-shutdown",   name: "runtime.shutdown",   description: "Shut down the CortexPrime platform", version: "1.0.0", enabled: true },
  { id: "rt-validation", name: "runtime.validation", description: "Validate runtime integrity",          version: "1.0.0", enabled: true },
  { id: "rt-health",     name: "runtime.health",     description: "Monitor runtime health",             version: "1.0.0", enabled: true },
  { id: "rt-metrics",    name: "runtime.metrics",    description: "Collect runtime metrics",            version: "1.0.0", enabled: true },
  { id: "rt-recovery",   name: "runtime.recovery",   description: "Recover from runtime failures",      version: "1.0.0", enabled: true },
]

export const CortexRuntimeCapability = {
  async getDefinitions(): Promise<RuntimeCapabilityDefinition[]> {
    return [...CortexRuntimeCapabilityDefinitions]
  },
  async getDefinition(name: string): Promise<RuntimeCapabilityDefinition | undefined> {
    return CortexRuntimeCapabilityDefinitions.find((d) => d.name === name)
  },
}