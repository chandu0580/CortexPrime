import type { ObservabilityCapabilityDefinition } from "./types"
import { generateId } from "./shared"

const capabilities = new Map<string, ObservabilityCapabilityDefinition>()

const builtInCapabilities: ObservabilityCapabilityDefinition[] = [
  { id: "obs-tracing", name: "observability.tracing", description: "Distributed tracing and span management", version: "1.0.0", enabled: true },
  { id: "obs-metrics", name: "observability.metrics", description: "Metrics collection, aggregation, and querying", version: "1.0.0", enabled: true },
  { id: "obs-audit", name: "observability.audit", description: "Audit trail recording and timeline building", version: "1.0.0", enabled: true },
  { id: "obs-replay", name: "observability.replay", description: "Execution replay and checkpoint management", version: "1.0.0", enabled: true },
  { id: "obs-diagnostics", name: "observability.diagnostics", description: "Diagnostic analysis and latency detection", version: "1.0.0", enabled: true },
  { id: "obs-correlation", name: "observability.correlation", description: "Event, worker, session, and mission correlation", version: "1.0.0", enabled: true },
]

for (const cap of builtInCapabilities) {
  capabilities.set(cap.id, cap)
}

export const ObservabilityCapability = {
  async isEnabled(name: string): Promise<boolean> {
    const cap = Array.from(capabilities.values()).find((c) => c.name === name)
    return cap?.enabled ?? false
  },

  async enable(name: string): Promise<ObservabilityCapabilityDefinition> {
    const cap = Array.from(capabilities.values()).find((c) => c.name === name)
    if (!cap) throw new Error(`Capability not found: ${name}`)
    const updated: ObservabilityCapabilityDefinition = { ...cap, enabled: true }
    capabilities.set(cap.id, updated)
    return updated
  },

  async disable(name: string): Promise<ObservabilityCapabilityDefinition> {
    const cap = Array.from(capabilities.values()).find((c) => c.name === name)
    if (!cap) throw new Error(`Capability not found: ${name}`)
    const updated: ObservabilityCapabilityDefinition = { ...cap, enabled: false }
    capabilities.set(cap.id, updated)
    return updated
  },

  async register(definition: Omit<ObservabilityCapabilityDefinition, "id">): Promise<ObservabilityCapabilityDefinition> {
    const id = generateId("cap")
    const full: ObservabilityCapabilityDefinition = { ...definition, id }
    capabilities.set(id, full)
    return full
  },

  async list(): Promise<ObservabilityCapabilityDefinition[]> {
    return Array.from(capabilities.values())
  },

  async get(name: string): Promise<ObservabilityCapabilityDefinition | null> {
    return Array.from(capabilities.values()).find((c) => c.name === name) ?? null
  },
}
