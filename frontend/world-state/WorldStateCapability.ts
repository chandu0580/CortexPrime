import type { CapabilityDefinition, CapabilityStage } from "@/capability-framework/types"

export class WorldStateCapability {
  private definition: CapabilityDefinition

  constructor(customConfig?: Partial<CapabilityDefinition>) {
    const now = new Date().toISOString()
    this.definition = {
      id: customConfig?.id ?? "world.state.capability",
      descriptor: {
        id: customConfig?.descriptor?.id ?? "world.state.capability",
        name: customConfig?.descriptor?.name ?? "World State Capability",
        type: customConfig?.descriptor?.type ?? "custom",
        version: customConfig?.descriptor?.version ?? "1.0.0",
        description: "World state system providing live operational state shared across every worker, runtime component, capability, mission, and intelligence module",
        category: customConfig?.descriptor?.category ?? "state",
        tags: customConfig?.descriptor?.tags ?? ["world-state", "state", "live", "operational", "shared"],
        icon: customConfig?.descriptor?.icon ?? "globe",
        provider: customConfig?.descriptor?.provider ?? "cortexprime",
        status: customConfig?.descriptor?.status ?? "active",
        createdAt: now,
        updatedAt: now,
      },
      stages: customConfig?.stages ?? this.createDefaultStages(),
      requirements: customConfig?.requirements ?? [
        { id: "req.state.init", type: "environment", key: "state_initialized", value: "required", description: "World state must be initialized before use", optional: false, validationHint: "Call createState() before any state operations" },
      ],
      constraints: customConfig?.constraints ?? [
        { id: "con.state.entries", type: "resource", key: "max_entries", value: 50000, description: "Maximum state entries in the world state", operator: "lte", severity: "warning" },
        { id: "con.state.snapshots", type: "resource", key: "max_snapshots", value: 50, description: "Maximum stored snapshots", operator: "lte", severity: "warning" },
      ],
      policies: customConfig?.policies ?? [
        { id: "pol.state.default", name: "Default State Allow", description: "Default allow policy for state operations", effect: "allow", resource: "state:*", actions: ["*"], conditions: {}, priority: 0, enabled: true },
      ],
      configuration: customConfig?.configuration ?? {
        settings: { maxEntries: 50000, maxSnapshotHistory: 50, autoSnapshotIntervalMs: 60000 },
        defaults: { scope: "global", owner: "system" },
        overrides: {},
        environment: {},
        features: { autoValidation: true, conflictDetection: true, autoSynchronization: false },
        timeouts: { transition: 1000, validation: 5000, sync: 10000 },
        limits: { maxEntries: 50000, maxSnapshotHistory: 50, maxTransitionHistory: 1000 },
      },
      dependencies: customConfig?.dependencies ?? [],
      metadata: customConfig?.metadata ?? {
        displayName: "World State Capability",
        description: "Live operational state shared across the entire CortexPrime platform",
        category: "state",
        tags: ["world-state", "operational", "shared"],
        provider: "cortexprime",
        homepage: "",
        documentation: "",
        license: "",
        maintainers: [],
        changelog: ["1.0.0 - Initial world state capability definition"],
      },
      createdAt: now,
      updatedAt: now,
    }
  }

  getDefinition(): CapabilityDefinition {
    return structuredClone(this.definition)
  }

  async register(): Promise<void> {
    const { CapabilityRegistry } = await import("@/capability-framework/CapabilityRegistry")
    await CapabilityRegistry.register(this.definition)
  }

  private createDefaultStages(): CapabilityStage[] {
    return [
      { id: "state.init", name: "Initialize World State", description: "Initialize the world state container", type: "setup", order: 1, timeoutMs: 1000, maxRetries: 1, inputKeys: ["name", "version"], outputKeys: ["worldStateId"], required: true, tags: ["state", "init"] },
      { id: "state.update", name: "Update State Entry", description: "Create or update a state entry with validation", type: "execute", order: 2, timeoutMs: 1000, maxRetries: 2, inputKeys: ["key", "value", "actor"], outputKeys: ["entryId", "version"], required: true, tags: ["state", "update"] },
      { id: "state.snapshot", name: "Create State Snapshot", description: "Capture point-in-time state snapshot", type: "execute", order: 3, timeoutMs: 3000, maxRetries: 1, inputKeys: ["label"], outputKeys: ["snapshotId"], required: false, tags: ["state", "snapshot"] },
      { id: "state.sync", name: "Synchronize State", description: "Synchronize state across scopes and resolve conflicts", type: "execute", order: 4, timeoutMs: 5000, maxRetries: 2, inputKeys: ["strategy"], outputKeys: ["syncId", "conflictsResolved"], required: false, tags: ["state", "sync"] },
      { id: "state.validate", name: "Validate World State", description: "Validate consistency, detect conflicts and missing references", type: "validate", order: 5, timeoutMs: 5000, maxRetries: 1, inputKeys: [], outputKeys: ["valid", "consistencyScore"], required: true, tags: ["state", "validate"] },
    ]
  }
}
