import type { SemanticMemoryEntry, MemoryRelationship, MemoryRelationshipType, MemoryPriority, MemoryScope } from "./types"
import { generateId } from "@/worker-framework/shared"
import { RedisClient } from "./RedisClient"

const ENTRY_KEY = "semantic:entry"
const SESSION_INDEX_KEY = "semantic:session"
const CATEGORY_INDEX_KEY = "semantic:category"

function serializeEntry(entry: SemanticMemoryEntry): Record<string, string> {
  return {
    id: entry.id,
    sessionId: entry.sessionId,
    type: entry.type,
    state: entry.state,
    priority: entry.priority,
    scope: entry.scope,
    tags: JSON.stringify(entry.tags),
    metadata: JSON.stringify(entry.metadata),
    createdAt: entry.createdAt,
    updatedAt: entry.updatedAt,
    expiresAt: entry.expiresAt ?? "",
    concept: entry.concept,
    definition: entry.definition,
    category: entry.category,
    aliases: JSON.stringify(entry.aliases),
    relationships: JSON.stringify(entry.relationships),
    confidence: String(entry.confidence),
  }
}

function deserializeEntry(data: Record<string, string>): SemanticMemoryEntry {
  return {
    id: data.id,
    sessionId: data.sessionId,
    type: "semantic",
    state: data.state as SemanticMemoryEntry["state"],
    priority: data.priority as MemoryPriority,
    scope: data.scope as MemoryScope,
    tags: JSON.parse(data.tags || "[]"),
    metadata: JSON.parse(data.metadata || "{}"),
    createdAt: data.createdAt,
    updatedAt: data.updatedAt,
    expiresAt: data.expiresAt || null,
    concept: data.concept,
    definition: data.definition,
    category: data.category,
    aliases: JSON.parse(data.aliases || "[]"),
    relationships: JSON.parse(data.relationships || "[]"),
    confidence: parseFloat(data.confidence) || 1.0,
  }
}

function reverseType(type: MemoryRelationshipType): MemoryRelationshipType {
  const map: Record<MemoryRelationshipType, MemoryRelationshipType> = {
    depends_on: "references",
    extends: "derived_from",
    supersedes: "derived_from",
    references: "depends_on",
    composed_of: "composed_of",
    derived_from: "extends",
  }
  return map[type] ?? "references"
}

export const SemanticMemory = {
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
    const now = new Date().toISOString()
    const entry: SemanticMemoryEntry = {
      id: generateId("mem-semantic"),
      sessionId,
      type: "semantic",
      state: "active",
      priority: priority ?? "medium",
      scope: scope ?? "session",
      tags: tags ?? [],
      metadata: metadata ?? {},
      createdAt: now,
      updatedAt: now,
      expiresAt: null,
      concept,
      definition,
      category,
      aliases: aliases ?? [],
      relationships: [],
      confidence: 1.0,
    }
    const client = RedisClient.getClient()
    if (client) {
      await client.hset(`${ENTRY_KEY}:${entry.id}`, serializeEntry(entry))
      await client.zadd(`${SESSION_INDEX_KEY}:${sessionId}`, Date.now(), entry.id)
      await client.zadd(`${CATEGORY_INDEX_KEY}:${category}`, Date.now(), entry.id)
    }
    return entry
  },

  async getConcept(conceptId: string): Promise<SemanticMemoryEntry | null> {
    const client = RedisClient.getClient()
    if (!client) return null
    const data = await client.hgetall(`${ENTRY_KEY}:${conceptId}`)
    if (!data || Object.keys(data).length === 0) return null
    return deserializeEntry(data)
  },

  async findConcept(sessionId: string, query: string): Promise<SemanticMemoryEntry[]> {
    const client = RedisClient.getClient()
    if (!client) return []
    const ids = await client.zrange(`${SESSION_INDEX_KEY}:${sessionId}`, 0, -1)
    const entries: SemanticMemoryEntry[] = []
    const q = query.toLowerCase()
    for (const id of ids) {
      const entry = await this.getConcept(id)
      if (!entry || entry.state !== "active") continue
      if (query.length > 0) {
        if (entry.concept.toLowerCase() === q) entries.push(entry)
        else if (entry.concept.toLowerCase().includes(q)) entries.push(entry)
        else if (entry.aliases.some((a) => a.toLowerCase() === q)) entries.push(entry)
        else if (entry.aliases.some((a) => a.toLowerCase().includes(q))) entries.push(entry)
        else if (entry.category.toLowerCase().includes(q)) entries.push(entry)
      } else {
        entries.push(entry)
      }
    }
    return entries
  },

  async updateConcept(
    conceptId: string,
    updates: Partial<Pick<SemanticMemoryEntry, "definition" | "category" | "confidence">>,
  ): Promise<SemanticMemoryEntry> {
    const entry = await this.getConcept(conceptId)
    if (!entry) throw new Error(`Semantic concept ${conceptId} not found`)
    const client = RedisClient.getClient()
    if (client) {
      if (updates.definition !== undefined) entry.definition = updates.definition
      if (updates.category !== undefined) entry.category = updates.category
      if (updates.confidence !== undefined) entry.confidence = updates.confidence
      entry.updatedAt = new Date().toISOString()
      await client.hset(`${ENTRY_KEY}:${entry.id}`, serializeEntry(entry))
    }
    return entry
  },

  async addAlias(conceptId: string, alias: string): Promise<void> {
    const entry = await this.getConcept(conceptId)
    if (!entry) throw new Error(`Semantic concept ${conceptId} not found`)
    const client = RedisClient.getClient()
    if (client) {
      if (!entry.aliases.includes(alias)) {
        entry.aliases.push(alias)
        entry.updatedAt = new Date().toISOString()
        await client.hset(`${ENTRY_KEY}:${entry.id}`, serializeEntry(entry))
      }
    }
  },

  async addRelationship(
    sourceId: string,
    targetId: string,
    type: MemoryRelationshipType,
    description: string,
  ): Promise<void> {
    const source = await this.getConcept(sourceId)
    const target = await this.getConcept(targetId)
    if (!source) throw new Error(`Source concept ${sourceId} not found`)
    if (!target) throw new Error(`Target concept ${targetId} not found`)

    const client = RedisClient.getClient()
    if (!client) return

    const relationship: MemoryRelationship = {
      targetId,
      type,
      description,
      createdAt: new Date().toISOString(),
    }
    source.relationships.push(relationship)
    source.updatedAt = new Date().toISOString()
    await client.hset(`${ENTRY_KEY}:${source.id}`, serializeEntry(source))

    const reverseRel: MemoryRelationship = {
      targetId: sourceId,
      type: reverseType(type),
      description,
      createdAt: new Date().toISOString(),
    }
    target.relationships.push(reverseRel)
    target.updatedAt = new Date().toISOString()
    await client.hset(`${ENTRY_KEY}:${target.id}`, serializeEntry(target))
  },

  async getConceptsByCategory(sessionId: string, category: string): Promise<SemanticMemoryEntry[]> {
    const client = RedisClient.getClient()
    if (!client) return []
    const ids = await client.zrange(`${CATEGORY_INDEX_KEY}:${category}`, 0, -1)
    const entries: SemanticMemoryEntry[] = []
    for (const id of ids) {
      const entry = await this.getConcept(id)
      if (entry && entry.sessionId === sessionId && entry.state === "active") {
        entries.push(entry)
      }
    }
    return entries
  },

  async archiveConcept(conceptId: string): Promise<void> {
    const entry = await this.getConcept(conceptId)
    if (!entry) throw new Error(`Semantic concept ${conceptId} not found`)
    const client = RedisClient.getClient()
    if (client) {
      entry.state = "archived"
      entry.updatedAt = new Date().toISOString()
      await client.hset(`${ENTRY_KEY}:${entry.id}`, serializeEntry(entry))
    }
  },

  async clearSession(sessionId: string): Promise<void> {
    const client = RedisClient.getClient()
    if (!client) return
    const ids = await client.zrange(`${SESSION_INDEX_KEY}:${sessionId}`, 0, -1)
    for (const id of ids) {
      await client.del(`${ENTRY_KEY}:${id}`)
    }
    await client.del(`${SESSION_INDEX_KEY}:${sessionId}`)
  },

  async countBySession(sessionId: string): Promise<number> {
    const entries = await this.findConcept(sessionId, "")
    return entries.length
  },

  async clearAll(): Promise<void> {
    const client = RedisClient.getClient()
    if (!client) return
    await RedisClient.flushPrefix("semantic:")
  },
}
