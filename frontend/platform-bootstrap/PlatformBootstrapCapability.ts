import type { BootstrapCapabilityDefinition } from "./types"

export const PlatformBootstrapCapabilityDefinitions: BootstrapCapabilityDefinition[] = [
  { id: "bootstrap-engine",      name: "platform.bootstrap",   description: "Bootstrap platform modules",              version: "1.0.0", enabled: true },
  { id: "bootstrap-startup",     name: "platform.startup",     description: "Coordinate platform startup sequence",     version: "1.0.0", enabled: true },
  { id: "bootstrap-lifecycle",   name: "platform.lifecycle",   description: "Manage bootstrap lifecycle transitions",   version: "1.0.0", enabled: true },
  { id: "bootstrap-validation",  name: "platform.validation",  description: "Validate bootstrap integrity",             version: "1.0.0", enabled: true },
  { id: "bootstrap-health",      name: "platform.health",      description: "Monitor bootstrap health",                version: "1.0.0", enabled: true },
  { id: "bootstrap-metrics",     name: "platform.metrics",     description: "Collect bootstrap metrics",               version: "1.0.0", enabled: true },
]

export const PlatformBootstrapCapability = {
  async getDefinitions(): Promise<BootstrapCapabilityDefinition[]> {
    return [...PlatformBootstrapCapabilityDefinitions]
  },

  async getDefinition(name: string): Promise<BootstrapCapabilityDefinition | undefined> {
    return PlatformBootstrapCapabilityDefinitions.find((d) => d.name === name)
  },
}