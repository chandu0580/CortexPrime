import type { ExecutiveCoordinationCapabilityDefinition } from "./types"
import { generateId } from "./shared"

const capabilities = new Map<string, ExecutiveCoordinationCapabilityDefinition>()

const builtInCapabilities: ExecutiveCoordinationCapabilityDefinition[] = [
  { id: "co-planning", name: "coordination.planning", description: "Coordination planning with stages, tasks, and sequencing", version: "1.0.0", enabled: true },
  { id: "co-routing", name: "coordination.routing", description: "Worker selection, routing, and capability matching", version: "1.0.0", enabled: true },
  { id: "co-delegation", name: "coordination.delegation", description: "Task delegation, reassignment, and revocation", version: "1.0.0", enabled: true },
  { id: "co-synchronization", name: "coordination.synchronization", description: "Worker synchronization with barriers and dependencies", version: "1.0.0", enabled: true },
  { id: "co-validation", name: "coordination.validation", description: "Coordination validation for ordering, assignments, dependencies, sync", version: "1.0.0", enabled: true },
  { id: "co-execution", name: "coordination.execution", description: "Execution evaluation, conflict resolution, and decision making", version: "1.0.0", enabled: true },
]

for (const cap of builtInCapabilities) {
  capabilities.set(cap.id, cap)
}

export const ExecutiveCoordinationCapability = {
  async isEnabled(name: string): Promise<boolean> {
    const cap = Array.from(capabilities.values()).find((c) => c.name === name)
    return cap?.enabled ?? false
  },

  async enable(name: string): Promise<ExecutiveCoordinationCapabilityDefinition> {
    const cap = Array.from(capabilities.values()).find((c) => c.name === name)
    if (!cap) throw new Error(`Capability not found: ${name}`)
    const updated: ExecutiveCoordinationCapabilityDefinition = { ...cap, enabled: true }
    capabilities.set(cap.id, updated)
    return updated
  },

  async disable(name: string): Promise<ExecutiveCoordinationCapabilityDefinition> {
    const cap = Array.from(capabilities.values()).find((c) => c.name === name)
    if (!cap) throw new Error(`Capability not found: ${name}`)
    const updated: ExecutiveCoordinationCapabilityDefinition = { ...cap, enabled: false }
    capabilities.set(cap.id, updated)
    return updated
  },

  async register(definition: Omit<ExecutiveCoordinationCapabilityDefinition, "id">): Promise<ExecutiveCoordinationCapabilityDefinition> {
    const id = generateId("cap")
    const full: ExecutiveCoordinationCapabilityDefinition = { ...definition, id }
    capabilities.set(id, full)
    return full
  },

  async list(): Promise<ExecutiveCoordinationCapabilityDefinition[]> {
    return Array.from(capabilities.values())
  },

  async get(name: string): Promise<ExecutiveCoordinationCapabilityDefinition | null> {
    return Array.from(capabilities.values()).find((c) => c.name === name) ?? null
  },
}
