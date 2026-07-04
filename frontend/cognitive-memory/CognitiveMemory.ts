import type { IEventBus, ITelemetry } from "@/platform/interfaces"
import type { CapabilityDefinition } from "@/capability-framework/types"
import type {
  MemorySession, MemoryEntryBase, WorkingMemoryEntry, EpisodicMemoryEntry,
  SemanticMemoryEntry, ProceduralMemoryEntry, MemoryAssociation, MemoryRelationshipType,
  MemorySnapshot, MemoryRecallRequest, MemoryRecallResult,
  MemoryType, MemoryPriority, MemoryScope, AssociationType, RecallStrategy,
  MemoryConfiguration, MemoryHealth,
  MemoryMetrics, MemoryEpisodeEvent,
  MemoryProcedureStep, RedisConfig,
} from "./types"
import { MemorySessionManager } from "./MemorySessionManager"
import { WorkingMemory } from "./WorkingMemory"
import { EpisodicMemory } from "./EpisodicMemory"
import { SemanticMemory } from "./SemanticMemory"
import { ProceduralMemory } from "./ProceduralMemory"
import { MemoryGraph } from "./MemoryGraph"
import { MemoryAssociationEngine } from "./MemoryAssociationEngine"
import { MemoryPolicyEngine } from "./MemoryPolicyEngine"
import { MemoryMetricsCollector } from "./MemoryMetricsCollector"
import { MemoryHealthManager } from "./MemoryHealthManager"
import { MemoryCapability } from "./MemoryCapability"
import { RedisClient } from "./RedisClient"
import { MemoryEventBus } from "./MemoryEventBus"

export class CognitiveMemory {
  private readonly systemId: string
  private readonly eventBus: IEventBus
  private readonly telemetry: ITelemetry
  private readonly capabilityDefinition: CapabilityDefinition
  private readonly config: MemoryConfiguration
  private readonly redisConfig?: RedisConfig
  private initialized: boolean = false
  private readonly startedAt: string

  constructor(
    eventBus: IEventBus,
    telemetry: ITelemetry,
    config?: Partial<MemoryConfiguration>,
    capabilityDefinition?: CapabilityDefinition,
    redisConfig?: RedisConfig,
  ) {
    this.systemId = `cognitive-memory-${Date.now()}`
    this.eventBus = eventBus
    this.telemetry = telemetry
    this.startedAt = new Date().toISOString()
    this.redisConfig = redisConfig

    const capability = new MemoryCapability(capabilityDefinition)
    this.capabilityDefinition = capability.getDefinition()

    this.config = {
      maxWorkingEntriesPerSession: 500,
      maxEpisodicEntriesPerSession: 200,
      maxSemanticEntriesPerSession: 500,
      maxProceduralEntriesPerSession: 100,
      defaultWorkingTTL: 300_000,
      maxAssociationStrength: 1.0,
      enableAutoExpiration: true,
      enableAutoSnapshot: false,
      graphTraversalMaxDepth: 5,
      policies: [
        { id: "mem.retention.default", name: "Default Retention", description: "Default retention policy", category: "retention", effect: "allow", rules: [{ field: "action", operator: "exists", value: null, message: "" }], priority: 0, enabled: true },
      ],
      ...config,
    }
  }

  async initialize(): Promise<void> {
    if (this.initialized) return

    if (this.redisConfig) {
      try {
        await RedisClient.connect(this.redisConfig)
        await this.telemetry.recordEvent("memory.redis.connected", {
          systemId: this.systemId,
          host: this.redisConfig.host,
          port: this.redisConfig.port,
        })
      } catch (error) {
        await this.telemetry.recordEvent("memory.redis.connection_failed", {
          systemId: this.systemId,
          error: error instanceof Error ? error.message : "Unknown error",
        })
      }
    }

    await MemoryMetricsCollector.initialize(this.systemId)
    await MemoryHealthManager.initialize(this.systemId)

    for (const policy of this.config.policies) {
      await MemoryPolicyEngine.registerPolicy(policy)
    }

    this.initialized = true

    await MemoryEventBus.publish(this.eventBus, "memory.system.initialized", {
      systemId: this.systemId,
      config: this.config,
      redisConnected: RedisClient.isConnected(),
    })
  }

  async shutdown(): Promise<void> {
    await MemoryEventBus.publish(this.eventBus, "memory.system.shutdown", {
      systemId: this.systemId,
    })
    await RedisClient.disconnect()
  }

  async createSession(
    contextId: string,
    scope?: MemoryScope,
    userId?: string | null,
    organizationId?: string | null,
  ): Promise<MemorySession> {
    this.requireInitialized()
    const session = await MemorySessionManager.createSession(contextId, scope, userId, organizationId)

    await MemoryMetricsCollector.setActiveSessions(
      this.systemId,
      (await MemorySessionManager.getActiveSessions()).length,
    )

    await MemoryEventBus.publish(this.eventBus, "memory.session.created", {
      systemId: this.systemId,
      sessionId: session.id,
      contextId,
    })

    return session
  }

  async closeSession(sessionId: string): Promise<void> {
    this.requireInitialized()
    await MemorySessionManager.closeSession(sessionId)

    await MemoryMetricsCollector.setActiveSessions(
      this.systemId,
      (await MemorySessionManager.getActiveSessions()).length,
    )

    await MemoryEventBus.publish(this.eventBus, "memory.session.closed", {
      systemId: this.systemId,
      sessionId,
    })
  }

  async storeWorking(
    sessionId: string,
    key: string,
    value: unknown,
    ttl?: number,
    priority?: MemoryPriority,
    scope?: MemoryScope,
    tags?: string[],
    metadata?: Record<string, string>,
  ): Promise<WorkingMemoryEntry> {
    this.requireInitialized()
    const entry = await WorkingMemory.createEntry(
      sessionId, key, value, ttl ?? this.config.defaultWorkingTTL,
      priority, scope, tags, metadata,
    )

    await MemorySessionManager.incrementEntryCount(sessionId)
    await MemoryMetricsCollector.recordEntry(this.systemId, "working")

    await MemoryGraph.addNode(entry.id, "working", key, {
      sessionId,
      key,
      ...metadata,
    })
    await MemoryMetricsCollector.recordGraphNode(this.systemId)

    await MemoryEventBus.publish(this.eventBus, "memory.entry.stored", {
      systemId: this.systemId,
      sessionId,
      entryId: entry.id,
      type: "working",
      key,
    })

    return entry
  }

  async retrieveWorking(sessionId: string, key: string): Promise<WorkingMemoryEntry | null> {
    this.requireInitialized()
    const start = Date.now()
    const entry = await WorkingMemory.retrieve(sessionId, key)
    await MemoryMetricsCollector.recordRecall(this.systemId, Date.now() - start)
    return entry
  }

  async storeEpisode(
    sessionId: string,
    missionId: string,
    summary: string,
    events: MemoryEpisodeEvent[],
    durationMs: number,
    priority?: MemoryPriority,
    scope?: MemoryScope,
    tags?: string[],
    metadata?: Record<string, string>,
  ): Promise<EpisodicMemoryEntry> {
    this.requireInitialized()
    const entry = await EpisodicMemory.storeEpisode(
      sessionId, missionId, summary, events, durationMs,
      priority, scope, tags, metadata,
    )

    await MemorySessionManager.incrementEntryCount(sessionId)
    await MemoryMetricsCollector.recordEntry(this.systemId, "episodic")

    await MemoryGraph.addNode(entry.id, "episodic", summary.slice(0, 50), {
      sessionId,
      missionId,
      episodeNumber: String(entry.episodeNumber),
      ...metadata,
    })
    await MemoryMetricsCollector.recordGraphNode(this.systemId)

    await MemoryEventBus.publish(this.eventBus, "memory.entry.stored", {
      systemId: this.systemId,
      sessionId,
      entryId: entry.id,
      type: "episodic",
      missionId,
    })

    return entry
  }

  async retrieveEpisode(episodeId: string): Promise<EpisodicMemoryEntry | null> {
    this.requireInitialized()
    const start = Date.now()
    const entry = await EpisodicMemory.retrieveEpisode(episodeId)
    await MemoryMetricsCollector.recordRecall(this.systemId, Date.now() - start)
    return entry
  }

  async registerConcept(
    sessionId: string,
    concept: string,
    definition: string,
    category: string,
    aliases?: string[],
    priority?: MemoryPriority,
    scope?: MemoryScope,
    tags?: string[],
    metadata?: Record<string, string>,
  ): Promise<SemanticMemoryEntry> {
    this.requireInitialized()
    const entry = await SemanticMemory.registerConcept(
      sessionId, concept, definition, category, aliases,
      priority, scope, tags, metadata,
    )

    await MemorySessionManager.incrementEntryCount(sessionId)
    await MemoryMetricsCollector.recordEntry(this.systemId, "semantic")

    await MemoryGraph.addNode(entry.id, "semantic", concept, {
      sessionId,
      category,
      ...metadata,
    })
    await MemoryMetricsCollector.recordGraphNode(this.systemId)

    await MemoryEventBus.publish(this.eventBus, "memory.concept.registered", {
      systemId: this.systemId,
      sessionId,
      entryId: entry.id,
      concept,
      category,
    })

    return entry
  }

  async findConcept(sessionId: string, query: string): Promise<SemanticMemoryEntry[]> {
    this.requireInitialized()
    const start = Date.now()
    const results = await SemanticMemory.findConcept(sessionId, query)
    await MemoryMetricsCollector.recordRecall(this.systemId, Date.now() - start)
    return results
  }

  async storeProcedure(
    sessionId: string,
    procedureName: string,
    procedureType: string,
    steps: Omit<MemoryProcedureStep, "id">[],
    inputs: string[],
    outputs: string[],
    conditions: string[],
    version?: string,
    priority?: MemoryPriority,
    scope?: MemoryScope,
    tags?: string[],
    metadata?: Record<string, string>,
  ): Promise<ProceduralMemoryEntry> {
    this.requireInitialized()
    const entry = await ProceduralMemory.storeProcedure(
      sessionId, procedureName, procedureType, steps,
      inputs, outputs, conditions, version,
      priority, scope, tags, metadata,
    )

    await MemorySessionManager.incrementEntryCount(sessionId)
    await MemoryMetricsCollector.recordEntry(this.systemId, "procedural")

    await MemoryGraph.addNode(entry.id, "procedural", procedureName, {
      sessionId,
      procedureType,
      version: entry.version,
      ...metadata,
    })
    await MemoryMetricsCollector.recordGraphNode(this.systemId)

    await MemoryEventBus.publish(this.eventBus, "memory.procedure.stored", {
      systemId: this.systemId,
      sessionId,
      entryId: entry.id,
      procedureName,
      procedureType,
    })

    return entry
  }

  async retrieveProcedure(procedureId: string): Promise<ProceduralMemoryEntry | null> {
    this.requireInitialized()
    const start = Date.now()
    const entry = await ProceduralMemory.retrieveProcedure(procedureId)
    await MemoryMetricsCollector.recordRecall(this.systemId, Date.now() - start)
    return entry
  }

  async associate(
    sourceId: string,
    targetId: string,
    type: AssociationType,
    strength?: number,
    metadata?: Record<string, string>,
  ): Promise<MemoryAssociation> {
    this.requireInitialized()

    const sourceNode = await MemoryGraph.findNodeByEntryId(sourceId)
    const targetNode = await MemoryGraph.findNodeByEntryId(targetId)

    if (sourceNode && targetNode) {
      await MemoryGraph.addEdge(sourceNode.id, targetNode.id, "references", strength)
      await MemoryMetricsCollector.recordGraphEdge(this.systemId)
    }

    const association = await MemoryAssociationEngine.createAssociation(
      sourceId, targetId, type, strength, metadata,
    )

    await MemoryMetricsCollector.recordAssociation(this.systemId)

    await MemoryEventBus.publish(this.eventBus, "memory.association.created", {
      systemId: this.systemId,
      associationId: association.id,
      sourceId,
      targetId,
      type,
    })

    return association
  }

  async link(
    parentId: string,
    childId: string,
    relationship: MemoryRelationshipType,
  ): Promise<void> {
    this.requireInitialized()

    const parentNode = await MemoryGraph.findNodeByEntryId(parentId)
    const childNode = await MemoryGraph.findNodeByEntryId(childId)

    if (!parentNode) throw new Error(`Parent entry ${parentId} has no graph node`)
    if (!childNode) throw new Error(`Child entry ${childId} has no graph node`)

    await MemoryGraph.addEdge(parentNode.id, childNode.id, relationship)
    await MemoryMetricsCollector.recordGraphEdge(this.systemId)

    if (relationship === "composed_of") {
      const parentEntry = await this.findEntryById(parentId)
      const childEntry = await this.findEntryById(childId)
      if (parentEntry && childEntry) {
        await MemoryAssociationEngine.createAssociation(
          parentId, childId, "hierarchical", 0.9,
          { relationship, parentType: parentEntry.type, childType: childEntry.type },
        )
        await MemoryMetricsCollector.recordAssociation(this.systemId)
      }
    }

    await MemoryEventBus.publish(this.eventBus, "memory.link.created", {
      systemId: this.systemId,
      parentId,
      childId,
      relationship,
    })
  }

  async recall(request: MemoryRecallRequest): Promise<MemoryRecallResult> {
    this.requireInitialized()
    const start = Date.now()

    const allEntries = await this.collectSessionEntries(request.sessionId)
    const filtered = this.filterEntries(allEntries, request)
    const sorted = this.sortEntries(filtered, request.strategy)
    const limited = sorted.slice(0, request.maxResults)

    const associations = await MemoryAssociationEngine.getAssociationsBySession(
      limited.map((e) => e.id),
    )

    const result: MemoryRecallResult = {
      request,
      entries: limited,
      totalMatches: filtered.length,
      returnedCount: limited.length,
      durationMs: Date.now() - start,
      associations,
    }

    await MemoryMetricsCollector.recordRecall(this.systemId, result.durationMs)

    return result
  }

  async snapshot(sessionId?: string): Promise<MemorySnapshot> {
    this.requireInitialized()

    let workingEntries: string[] = []
    let episodicEntries: string[] = []
    let semanticEntries: string[] = []
    let proceduralEntries: string[] = []

    if (sessionId) {
      workingEntries = (await WorkingMemory.getSessionEntries(sessionId)).map((e) => e.id)
      episodicEntries = (await EpisodicMemory.getEpisodesBySession(sessionId)).map((e) => e.id)
      semanticEntries = (await SemanticMemory.findConcept(sessionId, "")).map((e) => e.id)
      proceduralEntries = (await ProceduralMemory.findProceduresByTag(sessionId, "")).map((e) => e.id)
    }

    const snapshot: MemorySnapshot = {
      id: `snapshot-${Date.now()}`,
      sessionId: sessionId ?? "all",
      workingEntries,
      episodicEntries,
      semanticEntries,
      proceduralEntries,
      graphNodes: [],
      graphEdges: [],
      associations: [],
      capturedAt: new Date().toISOString(),
    }

    await MemoryMetricsCollector.recordSnapshot(this.systemId)

    await MemoryEventBus.publish(this.eventBus, "memory.snapshot.created", {
      systemId: this.systemId,
      sessionId,
      snapshotId: snapshot.id,
    })

    return snapshot
  }

  async expire(sessionId: string): Promise<{ workingExpired: string[]; total: number }> {
    this.requireInitialized()

    const workingExpired = await WorkingMemory.expire(sessionId)
    await MemoryMetricsCollector.recordExpired(this.systemId, workingExpired.length)

    if (workingExpired.length > 0) {
      await MemoryEventBus.publish(this.eventBus, "memory.entries.expired", {
        systemId: this.systemId,
        sessionId,
        count: workingExpired.length,
        types: ["working"],
      })
    }

    return { workingExpired, total: workingExpired.length }
  }

  async validate(): Promise<{ valid: boolean; errors: string[] }> {
    this.requireInitialized()
    const errors: string[] = []

    const orphans = await MemoryGraph.removeOrphanNodes()
    if (orphans.length > 0) {
      await MemoryMetricsCollector.recordOrphan(this.systemId, orphans.length)
    }

    const brokenEdges = await MemoryGraph.removeBrokenEdges()
    if (brokenEdges.length > 0) {
      errors.push(`Removed ${brokenEdges.length} broken graph edges`)
    }

    return { valid: brokenEdges.length === 0, errors }
  }

  async metrics(): Promise<MemoryMetrics> {
    this.requireInitialized()

    const density = await MemoryGraph.getGraphDensity()
    const activeSessions = (await MemorySessionManager.getActiveSessions()).length
    await MemoryMetricsCollector.setActiveSessions(this.systemId, activeSessions)

    return MemoryMetricsCollector.collect(this.systemId, density)
  }

  async health(): Promise<MemoryHealth> {
    this.requireInitialized()

    const workingCount = await WorkingMemory.countBySession("")
    const episodicCount = await EpisodicMemory.countBySession("")
    const semanticCount = await SemanticMemory.countBySession("")
    const proceduralCount = await ProceduralMemory.countBySession("")

    const totalEntries = workingCount + episodicCount + semanticCount + proceduralCount
    const orphanNodes = await MemoryGraph.removeOrphanNodes()
    const brokenEdges = await MemoryGraph.removeBrokenEdges()

    const allSessionIds = new Set<string>()
    for (const type of ["working", "episodic", "semantic", "procedural"] as const) {
      const entries = await this.collectAllEntriesByType(type)
      entries.forEach((e) => allSessionIds.add(e.sessionId))
    }

    await MemoryHealthManager.recordIntegrity(this.systemId, {
      totalEntries,
      activeEntries: totalEntries,
      expiredEntries: 0,
      orphanNodes: orphanNodes.length,
      brokenEdges: brokenEdges.length,
      expirationBacklog: 0,
    })

    return MemoryHealthManager.check(this.systemId)
  }

  async redisHealth(): Promise<{ connected: boolean; latencyMs: number }> {
    return RedisClient.healthCheck()
  }

  async storeMissionContext(missionId: string, context: Record<string, unknown>): Promise<void> {
    this.requireInitialized()
    
    const sessionId = `mission-${missionId}`
    const key = `mission:${missionId}:context`
    
    await this.storeWorking(
      sessionId,
      key,
      context,
      86400000, // 24 hours TTL
      "high",
      "global",
      ["mission", "context"],
      { missionId, type: "mission-context" },
    )
    
    await MemoryEventBus.publish(this.eventBus, "memory.mission.context-stored", {
      systemId: this.systemId,
      missionId,
      sessionId,
    })
  }

  async getMissionContext(missionId: string): Promise<Record<string, unknown> | null> {
    this.requireInitialized()
    
    const sessionId = `mission-${missionId}`
    const key = `mission:${missionId}:context`
    
    const entry = await this.retrieveWorking(sessionId, key)
    return entry ? (entry.value as Record<string, unknown>) : null
  }

  private async findEntryById(entryId: string): Promise<MemoryEntryBase | null> {
    const working = await WorkingMemory.retrieveById(entryId)
    if (working) return working
    const episodic = await EpisodicMemory.retrieveEpisode(entryId)
    if (episodic) return episodic
    const semantic = await SemanticMemory.getConcept(entryId)
    if (semantic) return semantic
    const procedural = await ProceduralMemory.retrieveProcedure(entryId)
    return procedural
  }

  private async collectSessionEntries(sessionId: string): Promise<MemoryEntryBase[]> {
    const entries: MemoryEntryBase[] = []

    const working = await WorkingMemory.getSessionEntries(sessionId)
    entries.push(...working)

    const episodic = await EpisodicMemory.getEpisodesBySession(sessionId)
    entries.push(...episodic)

    const semantic = await SemanticMemory.findConcept(sessionId, "")
    entries.push(...semantic)

    const procedural = await ProceduralMemory.findProceduresByTag(sessionId, "")
    entries.push(...procedural)

    return entries
  }

  private async collectAllEntriesByType(type: MemoryType): Promise<MemoryEntryBase[]> {
    switch (type) {
      case "working":
        return Array.from(await WorkingMemory.getSessionEntries(""))
      case "episodic":
        return Array.from(await EpisodicMemory.getEpisodesBySession(""))
      case "semantic":
        return []
      case "procedural":
        return []
    }
  }

  private filterEntries(entries: MemoryEntryBase[], request: MemoryRecallRequest): MemoryEntryBase[] {
    return entries.filter((e) => {
      if (!request.types.includes(e.type)) return false

      if (request.timeRangeMs !== null) {
        const entryTime = new Date(e.createdAt).getTime()
        const now = Date.now()
        if (now - entryTime > request.timeRangeMs) return false
      }

      if (request.query && request.query.length > 0 && e.type !== "working") {
        const q = request.query.toLowerCase()
        const metadataMatch = Object.values(e.metadata).some((v) => v.toLowerCase().includes(q))
        const tagsMatch = e.tags.some((t) => t.toLowerCase().includes(q))
        if (!metadataMatch && !tagsMatch) return false
      }

      return true
    })
  }

  private sortEntries(entries: MemoryEntryBase[], strategy: RecallStrategy): MemoryEntryBase[] {
    switch (strategy) {
      case "recent":
        return entries.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
      case "prioritized":
        return entries.sort((a, b) => {
          const order: Record<string, number> = { critical: 4, high: 3, medium: 2, low: 1 }
          return (order[b.priority] ?? 0) - (order[a.priority] ?? 0)
        })
      case "exact":
        return entries
      default:
        return entries.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
    }
  }

  private requireInitialized(): void {
    if (!this.initialized) {
      throw new Error("CognitiveMemory not initialized. Call initialize() first.")
    }
  }
}
