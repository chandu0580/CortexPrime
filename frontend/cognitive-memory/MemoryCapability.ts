import type { CapabilityDefinition, CapabilityStage } from "@/capability-framework/types"

export class MemoryCapability {
  private definition: CapabilityDefinition

  constructor(customConfig?: Partial<CapabilityDefinition>) {
    const now = new Date().toISOString()
    this.definition = {
      id: customConfig?.id ?? "memory.capability",
      descriptor: {
        id: customConfig?.descriptor?.id ?? "memory.capability",
        name: customConfig?.descriptor?.name ?? "Cognitive Memory Capability",
        type: customConfig?.descriptor?.type ?? "custom",
        version: customConfig?.descriptor?.version ?? "1.0.0",
        description: "Cognitive memory system for working, episodic, semantic, and procedural memory with graph-based relationships and deterministic recall",
        category: customConfig?.descriptor?.category ?? "memory",
        tags: customConfig?.descriptor?.tags ?? ["memory", "cognitive", "working", "episodic", "semantic", "procedural", "graph"],
        icon: customConfig?.descriptor?.icon ?? "database",
        provider: customConfig?.descriptor?.provider ?? "cortexprime",
        status: customConfig?.descriptor?.status ?? "active",
        createdAt: now,
        updatedAt: now,
      },
      stages: customConfig?.stages ?? this.createDefaultStages(),
      requirements: customConfig?.requirements ?? [
        { id: "req.mem.scope", type: "environment", key: "memory_scope", value: "session", description: "Default memory scope for operations", optional: true, validationHint: "Set memory scope to session, user, organization, or global" },
      ],
      constraints: customConfig?.constraints ?? [
        { id: "con.mem.entries", type: "resource", key: "max_entries_per_session", value: 10000, description: "Maximum memory entries per session", operator: "lte", severity: "warning" },
        { id: "con.mem.graph", type: "resource", key: "max_graph_depth", value: 10, description: "Maximum graph traversal depth", operator: "lte", severity: "warning" },
      ],
      policies: customConfig?.policies ?? [
        { id: "pol.mem.default", name: "Default Memory Allow", description: "Default allow policy for memory operations", effect: "allow", resource: "memory:*", actions: ["*"], conditions: {}, priority: 0, enabled: true },
      ],
      configuration: customConfig?.configuration ?? {
        settings: { defaultWorkingTTL: 300000, maxAssociationStrength: 1.0, graphTraversalMaxDepth: 5 },
        defaults: { scope: "session", priority: "medium" },
        overrides: {},
        environment: {},
        features: { autoExpiration: true, autoSnapshot: false, graphAutoCleanup: true },
        timeouts: { store: 1000, recall: 2000, traverse: 5000 },
        limits: { maxWorkingEntriesPerSession: 500, maxEpisodicPerSession: 200, maxSemanticPerSession: 500, maxProceduralPerSession: 100, graphTraversalMaxDepth: 10 },
      },
      dependencies: customConfig?.dependencies ?? [],
      metadata: customConfig?.metadata ?? {
        displayName: "Cognitive Memory Capability",
        description: "Enterprise cognitive memory system with four memory types and graph relationships",
        category: "memory",
        tags: ["memory", "cognitive", "enterprise"],
        provider: "cortexprime",
        homepage: "",
        documentation: "",
        license: "",
        maintainers: [],
        changelog: ["1.0.0 - Initial cognitive memory capability definition"],
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
      { id: "mem.store", name: "Store Memory Entry", description: "Store an entry in the specified memory type", type: "execute", order: 1, timeoutMs: 1000, maxRetries: 1, inputKeys: ["sessionId", "type", "data"], outputKeys: ["entryId"], required: true, tags: ["memory", "store"] },
      { id: "mem.recall", name: "Recall Memory Entry", description: "Recall entries from memory based on query and strategy", type: "execute", order: 2, timeoutMs: 2000, maxRetries: 2, inputKeys: ["sessionId", "query", "strategy"], outputKeys: ["entries", "associations"], required: true, tags: ["memory", "recall"] },
      { id: "mem.associate", name: "Create Association", description: "Create deterministic associations between memory entries", type: "execute", order: 3, timeoutMs: 1000, maxRetries: 1, inputKeys: ["sourceId", "targetId", "type"], outputKeys: ["associationId"], required: true, tags: ["memory", "association"] },
      { id: "mem.snapshot", name: "Create Memory Snapshot", description: "Capture point-in-time snapshot of memory state", type: "execute", order: 4, timeoutMs: 3000, maxRetries: 1, inputKeys: ["sessionId"], outputKeys: ["snapshotId"], required: false, tags: ["memory", "snapshot"] },
      { id: "mem.expire", name: "Expire Memory Entries", description: "Expire and clean up stale memory entries", type: "cleanup", order: 5, timeoutMs: 5000, maxRetries: 1, inputKeys: ["sessionId"], outputKeys: ["expiredCount"], required: true, tags: ["memory", "cleanup"] },
    ]
  }
}
