import type { CapabilityDefinition, CapabilityStage } from "@/capability-framework/types"

export class KnowledgeGraphCapability {
  private definition: CapabilityDefinition

  constructor(customConfig?: Partial<CapabilityDefinition>) {
    const now = new Date().toISOString()
    this.definition = {
      id: customConfig?.id ?? "knowledge.graph.capability",
      descriptor: {
        id: customConfig?.descriptor?.id ?? "knowledge.graph.capability",
        name: customConfig?.descriptor?.name ?? "Knowledge Graph Capability",
        type: customConfig?.descriptor?.type ?? "custom",
        version: customConfig?.descriptor?.version ?? "1.0.0",
        description: "Enterprise knowledge graph connecting entities, concepts, relationships, evidence, procedures, memories, missions, capabilities, workers, and world state",
        category: customConfig?.descriptor?.category ?? "knowledge",
        tags: customConfig?.descriptor?.tags ?? ["knowledge", "graph", "entities", "relationships", "traversal", "inference"],
        icon: customConfig?.descriptor?.icon ?? "network",
        provider: customConfig?.descriptor?.provider ?? "cortexprime",
        status: customConfig?.descriptor?.status ?? "active",
        createdAt: now,
        updatedAt: now,
      },
      stages: customConfig?.stages ?? this.createDefaultStages(),
      requirements: customConfig?.requirements ?? [
        { id: "req.kg.entities", type: "capability", key: "entity_management", value: "required", description: "Entity management capability for registering and querying entities", optional: false, validationHint: "Entity management must be available" },
      ],
      constraints: customConfig?.constraints ?? [
        { id: "con.kg.entities", type: "resource", key: "max_entities", value: 50000, description: "Maximum entities in the knowledge graph", operator: "lte", severity: "warning" },
        { id: "con.kg.traversal", type: "resource", key: "max_traversal_depth", value: 10, description: "Maximum graph traversal depth", operator: "lte", severity: "warning" },
      ],
      policies: customConfig?.policies ?? [
        { id: "pol.kg.default", name: "Default Knowledge Graph Allow", description: "Default allow policy for knowledge graph operations", effect: "allow", resource: "knowledge:*", actions: ["*"], conditions: {}, priority: 0, enabled: true },
      ],
      configuration: customConfig?.configuration ?? {
        settings: { maxEntities: 50000, maxTraversalDepth: 10, defaultConfidence: 1.0 },
        defaults: { category: "custom", source: "system" },
        overrides: {},
        environment: {},
        features: { autoInference: true, cycleDetection: true, duplicateDetection: true },
        timeouts: { traversal: 5000, inference: 10000, validation: 5000 },
        limits: { maxEntities: 50000, maxRelationships: 200000, maxTraversalDepth: 10 },
      },
      dependencies: customConfig?.dependencies ?? [],
      metadata: customConfig?.metadata ?? {
        displayName: "Knowledge Graph Capability",
        description: "Enterprise knowledge graph for entity relationship management, traversal, and deterministic inference",
        category: "knowledge",
        tags: ["knowledge", "graph", "enterprise"],
        provider: "cortexprime",
        homepage: "",
        documentation: "",
        license: "",
        maintainers: [],
        changelog: ["1.0.0 - Initial knowledge graph capability definition"],
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
      { id: "kg.register_entity", name: "Register Entity", description: "Register a new entity in the knowledge graph", type: "setup", order: 1, timeoutMs: 1000, maxRetries: 1, inputKeys: ["name", "type", "category"], outputKeys: ["entityId"], required: true, tags: ["knowledge", "entity"] },
      { id: "kg.create_relationship", name: "Create Relationship", description: "Create a typed relationship between entities", type: "execute", order: 2, timeoutMs: 1000, maxRetries: 2, inputKeys: ["sourceId", "targetId", "type"], outputKeys: ["relationshipId"], required: true, tags: ["knowledge", "relationship"] },
      { id: "kg.traverse", name: "Traverse Graph", description: "Traverse the graph using BFS, DFS, or shortest path", type: "execute", order: 3, timeoutMs: 5000, maxRetries: 1, inputKeys: ["startNodeId", "strategy", "maxDepth"], outputKeys: ["paths", "visitedNodes"], required: false, tags: ["knowledge", "traversal"] },
      { id: "kg.infer", name: "Infer Relationships", description: "Run deterministic inference to derive implicit relationships", type: "execute", order: 4, timeoutMs: 10000, maxRetries: 2, inputKeys: [], outputKeys: ["inferences", "clusters"], required: false, tags: ["knowledge", "inference"] },
      { id: "kg.validate", name: "Validate Graph", description: "Validate graph integrity, detect cycles, duplicates, and broken links", type: "validate", order: 5, timeoutMs: 5000, maxRetries: 1, inputKeys: [], outputKeys: ["valid", "consistencyScore"], required: true, tags: ["knowledge", "validate"] },
    ]
  }
}
