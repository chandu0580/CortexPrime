import type { IEventBus, ITelemetry } from "@/platform/interfaces"
import type { CapabilityDefinition } from "@/capability-framework/types"
import type {
  KnowledgeEntity, KnowledgeRelationship, KnowledgeInference,
  EntityCategory, RelationshipType, TraversalStrategy,
  KnowledgeRequest, KnowledgeResult,
  GraphMetrics, GraphHealth, GraphConfiguration,
  GraphTraversal, GraphPath, GraphNeighborhood, GraphNode,
  GraphSnapshot, Neo4jConfig,
} from "./types"
import type { GraphValidation } from "./GraphValidationEngine"
import { EntityManager } from "./EntityManager"
import { RelationshipManager } from "./RelationshipManager"
import { GraphManager } from "./GraphManager"
import { GraphTraversalEngine } from "./GraphTraversalEngine"
import { GraphInferenceEngine } from "./GraphInferenceEngine"
import { GraphValidationEngine } from "./GraphValidationEngine"
import { GraphPolicyEngine } from "./GraphPolicyEngine"
import { GraphMetricsCollector } from "./GraphMetricsCollector"
import { GraphHealthManager } from "./GraphHealthManager"
import { KnowledgeGraphCapability } from "./KnowledgeGraphCapability"
import { Neo4jClient } from "./Neo4jClient"

export class KnowledgeGraph {
  private readonly systemId: string
  private readonly eventBus: IEventBus
  private readonly telemetry: ITelemetry
  private readonly capabilityDefinition: CapabilityDefinition
  private readonly config: GraphConfiguration
  private readonly neo4jConfig?: Neo4jConfig
  private initialized: boolean = false

  constructor(
    eventBus: IEventBus,
    telemetry: ITelemetry,
    config?: Partial<GraphConfiguration>,
    capabilityDefinition?: CapabilityDefinition,
    neo4jConfig?: Neo4jConfig,
  ) {
    this.systemId = `knowledge-graph-${Date.now()}`
    this.eventBus = eventBus
    this.telemetry = telemetry
    this.neo4jConfig = neo4jConfig

    const capability = new KnowledgeGraphCapability(capabilityDefinition)
    this.capabilityDefinition = capability.getDefinition()

    this.config = {
      maxEntities: 50000,
      maxRelationships: 200000,
      maxTraversalDepth: 10,
      enableAutoInference: true,
      enableCycleDetection: true,
      defaultConfidence: 1.0,
      policies: [
        { id: "kg.default.allow", name: "Default Allow", description: "Default allow for knowledge graph operations", category: "integrity", effect: "allow", rules: [{ field: "action", operator: "exists", value: null, message: "" }], priority: 0, enabled: true },
      ],
      ...config,
    }
  }

  async initialize(): Promise<void> {
    if (this.initialized) return

    if (this.neo4jConfig) {
      try {
        await Neo4jClient.connect(this.neo4jConfig)
        await Neo4jClient.createIndexes()
        await this.telemetry.recordEvent("knowledge.neo4j.connected", {
          systemId: this.systemId,
          uri: this.neo4jConfig.uri,
          database: this.neo4jConfig.database ?? "neo4j",
        })
      } catch (error) {
        await this.telemetry.recordEvent("knowledge.neo4j.connection_failed", {
          systemId: this.systemId,
          error: error instanceof Error ? error.message : "Unknown error",
        })
      }
    }

    await GraphMetricsCollector.initialize(this.systemId)
    await GraphHealthManager.initialize(this.systemId)

    for (const policy of this.config.policies) {
      await GraphPolicyEngine.registerPolicy(policy)
    }

    this.initialized = true

    await this.eventBus.publish("knowledge", "knowledge.graph.initialized", {
      systemId: this.systemId,
      neo4jConnected: Neo4jClient.isConnected(),
    })
  }

  async shutdown(): Promise<void> {
    await this.eventBus.publish("knowledge", "knowledge.graph.shutdown", {
      systemId: this.systemId,
    })
    await Neo4jClient.disconnect()
  }

  async registerEntity(
    name: string,
    type: string,
    category: EntityCategory,
    description: string,
    properties?: Record<string, unknown>,
    tags?: string[],
    source?: string,
    confidence?: number,
    aliases?: string[],
  ): Promise<KnowledgeEntity> {
    this.requireInitialized()

    const policyResult = await GraphPolicyEngine.evaluate({
      action: "register_entity", name, type, category,
    })
    if (!policyResult.allowed) {
      throw new Error(`Policy denied entity registration: ${policyResult.reasons.join(", ")}`)
    }

    const entity = await EntityManager.registerEntity(name, type, category, description, properties, tags, source, confidence, aliases)
    await GraphManager.addNode(entity)

    await GraphMetricsCollector.recordEntity(this.systemId, "active")
    await GraphMetricsCollector.recordGraphNode(this.systemId)
    await GraphMetricsCollector.recordConfidence(this.systemId, entity.confidence)

    await this.eventBus.publish("knowledge", "knowledge.entity.registered", {
      systemId: this.systemId, entityId: entity.id, name, type, category,
    })

    return entity
  }

  async updateEntity(entityId: string, updates: Partial<Omit<KnowledgeEntity, "id" | "createdAt">>): Promise<KnowledgeEntity> {
    this.requireInitialized()
    const entity = await EntityManager.updateEntity(entityId, updates)
    return entity
  }

  async removeEntity(entityId: string): Promise<void> {
    this.requireInitialized()
    await EntityManager.removeEntity(entityId)
    const node = await GraphManager.getNodeByEntityId(entityId)
    if (node) await GraphManager.removeNode(node.id)

    await this.eventBus.publish("knowledge", "knowledge.entity.removed", {
      systemId: this.systemId, entityId,
    })
  }

  async findEntity(entityId: string): Promise<KnowledgeEntity | null> {
    this.requireInitialized()
    return EntityManager.findEntity(entityId)
  }

  async queryEntities(query: { field?: string; value?: string; category?: EntityCategory; tag?: string; name?: string }): Promise<KnowledgeEntity[]> {
    this.requireInitialized()
    return EntityManager.queryEntities(query)
  }

  async createRelationship(
    sourceId: string, targetId: string, type: RelationshipType,
    weight?: number, confidence?: number, properties?: Record<string, string>, bidirectional?: boolean,
  ): Promise<KnowledgeRelationship> {
    this.requireInitialized()

    const policyResult = await GraphPolicyEngine.evaluate({
      action: "create_relationship", sourceId, targetId, type,
    })
    if (!policyResult.allowed) {
      throw new Error(`Policy denied relationship creation: ${policyResult.reasons.join(", ")}`)
    }

    const relationship = await RelationshipManager.createRelationship(sourceId, targetId, type, weight, confidence, properties, bidirectional)
    await GraphManager.addEdge(relationship)

    await GraphMetricsCollector.recordRelationship(this.systemId)
    await GraphMetricsCollector.recordGraphEdge(this.systemId)

    await this.eventBus.publish("knowledge", "knowledge.relationship.created", {
      systemId: this.systemId, relationshipId: relationship.id, sourceId, targetId, type,
    })

    return relationship
  }

  async removeRelationship(relationshipId: string): Promise<void> {
    this.requireInitialized()
    await RelationshipManager.removeRelationship(relationshipId)

    await this.eventBus.publish("knowledge", "knowledge.relationship.removed", {
      systemId: this.systemId, relationshipId,
    })
  }

  async findRelationships(entityId?: string, type?: RelationshipType): Promise<KnowledgeRelationship[]> {
    this.requireInitialized()
    return RelationshipManager.findRelationships(entityId, type)
  }

  async traverse(
    startEntityId: string, strategy: TraversalStrategy = "bfs", maxDepth: number = 5,
  ): Promise<GraphTraversal> {
    this.requireInitialized()
    const startNode = await GraphManager.getNodeByEntityId(startEntityId)
    if (!startNode) throw new Error(`No graph node for entity ${startEntityId}`)

    const startTime = Date.now()
    let paths: GraphPath[] = []

    switch (strategy) {
      case "bfs":
        paths = await GraphTraversalEngine.bfs(startNode.id, maxDepth)
        break
      case "dfs":
        paths = await GraphTraversalEngine.dfs(startNode.id, maxDepth)
        break
      case "shortest_path":
        break
      case "all_paths":
        paths = await GraphTraversalEngine.bfs(startNode.id, maxDepth)
        break
    }

    const visitedNodes = new Set<string>()
    const visitedEdges = new Set<string>()
    for (const path of paths) {
      path.nodes.forEach((n) => visitedNodes.add(n.id))
      path.edges.forEach((e) => visitedEdges.add(e.id))
    }

    await GraphMetricsCollector.recordTraversal(this.systemId)

    return {
      strategy,
      startNodeId: startNode.id,
      maxDepth,
      paths,
      visitedNodes: Array.from(visitedNodes),
      visitedEdges: Array.from(visitedEdges),
      durationMs: Date.now() - startTime,
    }
  }

  async shortestPath(fromEntityId: string, toEntityId: string): Promise<GraphPath | null> {
    this.requireInitialized()
    const fromNode = await GraphManager.getNodeByEntityId(fromEntityId)
    const toNode = await GraphManager.getNodeByEntityId(toEntityId)
    if (!fromNode) throw new Error(`No graph node for entity ${fromEntityId}`)
    if (!toNode) throw new Error(`No graph node for entity ${toEntityId}`)
    return GraphTraversalEngine.shortestPath(fromNode.id, toNode.id)
  }

  async neighborhood(entityId: string, depth: number = 1): Promise<GraphNeighborhood> {
    this.requireInitialized()
    const node = await GraphManager.getNodeByEntityId(entityId)
    if (!node) throw new Error(`No graph node for entity ${entityId}`)
    return GraphTraversalEngine.neighborhood(node.id, depth)
  }

  async infer(): Promise<KnowledgeInference[]> {
    this.requireInitialized()
    const inferred = await GraphInferenceEngine.inferRelationships()
    await GraphMetricsCollector.recordInference(this.systemId, inferred.length)

    const clusters = await GraphInferenceEngine.inferClusters()
    await GraphMetricsCollector.recordCluster(this.systemId, clusters.length)

    await this.eventBus.publish("knowledge", "knowledge.inference.completed", {
      systemId: this.systemId, inferencesCreated: inferred.length, clustersFound: clusters.length,
    })

    return inferred
  }

  async detectCycles(): Promise<GraphNode[][]> {
    this.requireInitialized()
    return GraphInferenceEngine.detectCycles()
  }

  async validate(): Promise<GraphValidation> {
    this.requireInitialized()
    await GraphMetricsCollector.recordValidation(this.systemId)

    const validation = await GraphValidationEngine.validate()
    const components = await GraphManager.findConnectedComponents()

    const duplicates = await EntityManager.findDuplicates()
    await GraphMetricsCollector.setDuplicateEntities(this.systemId, duplicates.length)

    const orphans = await GraphManager.findOrphanNodes()
    await GraphMetricsCollector.setOrphanNodes(this.systemId, orphans.length)

    await GraphHealthManager.recordIntegrity(this.systemId, {
      totalEntities: validation.totalEntities,
      totalRelationships: validation.totalRelationships,
      orphanNodes: validation.orphanNodes.length,
      invalidEdges: validation.invalidRelationships.length,
      duplicateEntities: duplicates.length,
      disconnectedComponents: components.length,
      consistencyScore: validation.consistencyScore,
    })

    if (!validation.valid) {
      await this.eventBus.publish("knowledge", "knowledge.validation.issues", {
        systemId: this.systemId, issues: {
          brokenLinks: validation.brokenLinks.length,
          duplicates: validation.duplicateEntities.length,
          invalidRelationships: validation.invalidRelationships.length,
          cycles: validation.cycles,
          orphanNodes: validation.orphanNodes.length,
        },
      })
    }

    return validation
  }

  async getGraphDensity(): Promise<number> {
    return GraphManager.getGraphDensity()
  }

  async getConnectedComponents(): Promise<GraphNode[][]> {
    return GraphTraversalEngine.connectedComponents()
  }

  async takeSnapshot(): Promise<GraphSnapshot> {
    this.requireInitialized()
    const entities = await EntityManager.getActiveEntities()
    await RelationshipManager.getAll()
    const nodes = await GraphManager.countNodes()
    const edges = await GraphManager.countEdges()

    return {
      id: `kg-snapshot-${Date.now()}`,
      label: `Snapshot ${new Date().toISOString()}`,
      nodeCount: nodes,
      edgeCount: edges,
      entityCount: entities.length,
      capturedAt: new Date().toISOString(),
    }
  }

  async request(request: KnowledgeRequest): Promise<KnowledgeResult> {
    this.requireInitialized()
    const startTime = Date.now()

    try {
      switch (request.type) {
        case "register_entity": {
          if (!request.entity) throw new Error("Entity data required")
          const entity = await this.registerEntity(
            request.entity.name, request.entity.type, request.entity.category,
            request.entity.description, request.entity.properties,
            request.entity.tags, request.entity.source, request.entity.confidence, request.entity.aliases,
          )
          return { success: true, data: entity, error: null, durationMs: Date.now() - startTime, timestamp: new Date().toISOString() }
        }
        case "create_relationship": {
          if (!request.relationship) throw new Error("Relationship data required")
          const rel = await this.createRelationship(
            request.relationship.sourceId, request.relationship.targetId,
            request.relationship.type, request.relationship.weight,
            request.relationship.confidence, request.relationship.properties,
            request.relationship.bidirectional,
          )
          return { success: true, data: rel, error: null, durationMs: Date.now() - startTime, timestamp: new Date().toISOString() }
        }
        case "traverse": {
          if (!request.traversal) throw new Error("Traversal data required")
          const result = await this.traverse(request.traversal.startEntityId, request.traversal.strategy, request.traversal.maxDepth)
          return { success: true, data: result, error: null, durationMs: Date.now() - startTime, timestamp: new Date().toISOString() }
        }
        case "infer": {
          const inferred = await this.infer()
          return { success: true, data: inferred, error: null, durationMs: Date.now() - startTime, timestamp: new Date().toISOString() }
        }
        case "validate": {
          const validation = await this.validate()
          return { success: true, data: validation, error: null, durationMs: Date.now() - startTime, timestamp: new Date().toISOString() }
        }
        case "query_entity": {
          if (!request.query) throw new Error("Query data required")
          const entities = await this.queryEntities({ field: request.query.field, value: request.query.value })
          return { success: true, data: entities, error: null, durationMs: Date.now() - startTime, timestamp: new Date().toISOString() }
        }
        case "query_relationship": {
          const relationships = await this.findRelationships()
          return { success: true, data: relationships, error: null, durationMs: Date.now() - startTime, timestamp: new Date().toISOString() }
        }
        default:
          throw new Error(`Unknown request type: ${request.type}`)
      }
    } catch (err) {
      return {
        success: false, data: null,
        error: err instanceof Error ? err.message : String(err),
        durationMs: Date.now() - startTime,
        timestamp: new Date().toISOString(),
      }
    }
  }

  async metrics(): Promise<GraphMetrics> {
    this.requireInitialized()
    const density = await GraphManager.getGraphDensity()
    const components = await GraphManager.findConnectedComponents()
    return GraphMetricsCollector.collect(this.systemId, density, components.length)
  }

  async health(): Promise<GraphHealth> {
    this.requireInitialized()
    return GraphHealthManager.check(this.systemId)
  }

  async neo4jHealth(): Promise<{ connected: boolean; latencyMs: number }> {
    return Neo4jClient.healthCheck()
  }

  async createMissionEntity(missionId: string, data: {
    name: string
    description?: string
    status: string
    startedAt: string
  }): Promise<KnowledgeEntity> {
    this.requireInitialized()
    
    const entity = await this.registerEntity(
      data.name,
      "mission",
      "state",
      data.description || `Mission ${missionId}`,
      { missionId, status: data.status, startedAt: data.startedAt },
      ["mission", data.status],
      "mission-runtime",
      1.0,
      [missionId],
    )
    
    await this.eventBus.publish("knowledge", "knowledge.mission.entity-created", {
      systemId: this.systemId,
      missionId,
      entityId: entity.id,
    })
    
    return entity
  }

  async updateMissionEntity(missionId: string, updates: {
    status?: string
    completedAt?: string
    [key: string]: unknown
  }): Promise<void> {
    this.requireInitialized()
    
    const entities = await this.queryEntities({ field: "missionId", value: missionId })
    const missionEntity = entities.find(e => e.type === "mission")
    
    if (missionEntity) {
      await this.updateEntity(missionEntity.id, {
        properties: { ...missionEntity.properties, ...updates },
        tags: [...(missionEntity.tags || []), updates.status].filter(Boolean) as string[],
      })
      
      await this.eventBus.publish("knowledge", "knowledge.mission.entity-updated", {
        systemId: this.systemId,
        missionId,
        entityId: missionEntity.id,
        updates,
      })
    }
  }

  private requireInitialized(): void {
    if (!this.initialized) {
      throw new Error("KnowledgeGraph not initialized. Call initialize() first.")
    }
  }
}
