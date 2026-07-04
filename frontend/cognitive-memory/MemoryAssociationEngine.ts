import type { MemoryAssociation, AssociationType, MemoryEntryBase } from "./types"
import { generateId } from "@/worker-framework/shared"
import { RedisClient } from "./RedisClient"

const ASSOC_KEY = "assoc:entry"
const SOURCE_INDEX_KEY = "assoc:source"
const TARGET_INDEX_KEY = "assoc:target"
const TYPE_INDEX_KEY = "assoc:type"
const PAIR_INDEX_KEY = "assoc:pair"

function serializeAssociation(assoc: MemoryAssociation): Record<string, string> {
  return {
    id: assoc.id,
    sourceId: assoc.sourceId,
    targetId: assoc.targetId,
    type: assoc.type,
    strength: String(assoc.strength),
    metadata: JSON.stringify(assoc.metadata),
    createdAt: assoc.createdAt,
  }
}

function deserializeAssociation(data: Record<string, string>): MemoryAssociation {
  return {
    id: data.id,
    sourceId: data.sourceId,
    targetId: data.targetId,
    type: data.type as AssociationType,
    strength: parseFloat(data.strength) || 1.0,
    metadata: JSON.parse(data.metadata || "{}"),
    createdAt: data.createdAt,
  }
}

export const MemoryAssociationEngine = {
  async createAssociation(
    sourceId: string,
    targetId: string,
    type: AssociationType,
    strength: number = 1.0,
    metadata?: Record<string, string>,
  ): Promise<MemoryAssociation> {
    const client = RedisClient.getClient()
    if (client) {
      const existingId = await client.hget(`${PAIR_INDEX_KEY}:${sourceId}:${targetId}`, type)
      if (existingId) {
        const existingData = await client.hgetall(`${ASSOC_KEY}:${existingId}`)
        if (existingData && Object.keys(existingData).length > 0) {
          return deserializeAssociation(existingData)
        }
      }
    }

    const association: MemoryAssociation = {
      id: generateId("mem-assoc"),
      sourceId,
      targetId,
      type,
      strength: Math.min(Math.max(strength, 0), 1),
      metadata: metadata ?? {},
      createdAt: new Date().toISOString(),
    }

    if (client) {
      await client.hset(`${ASSOC_KEY}:${association.id}`, serializeAssociation(association))
      await client.sadd(`${SOURCE_INDEX_KEY}:${sourceId}`, association.id)
      await client.sadd(`${TARGET_INDEX_KEY}:${targetId}`, association.id)
      await client.sadd(`${TYPE_INDEX_KEY}:${type}`, association.id)
      await client.hset(`${PAIR_INDEX_KEY}:${sourceId}:${targetId}`, { [type]: association.id })
    }
    return association
  },

  async findBySameSession(entries: MemoryEntryBase[], sessionId: string): Promise<MemoryAssociation[]> {
    const sessionEntries = entries.filter((e) => e.sessionId === sessionId)
    const created: MemoryAssociation[] = []

    for (let i = 0; i < sessionEntries.length; i++) {
      for (let j = i + 1; j < sessionEntries.length; j++) {
        const assoc = await this.createAssociation(
          sessionEntries[i].id,
          sessionEntries[j].id,
          "same_session",
          0.8,
          { sessionId },
        )
        created.push(assoc)
      }
    }
    return created
  },

  async findBySameUser(entries: MemoryEntryBase[], userId: string): Promise<MemoryAssociation[]> {
    const userEntries = entries.filter((e) => (e.metadata["userId"] ?? "") === userId)
    const created: MemoryAssociation[] = []

    for (let i = 0; i < userEntries.length; i++) {
      for (let j = i + 1; j < userEntries.length; j++) {
        const assoc = await this.createAssociation(
          userEntries[i].id,
          userEntries[j].id,
          "same_user",
          0.7,
          { userId },
        )
        created.push(assoc)
      }
    }
    return created
  },

  async findBySameCapability(entries: MemoryEntryBase[], capabilityId: string): Promise<MemoryAssociation[]> {
    const capEntries = entries.filter((e) => (e.metadata["capabilityId"] ?? "") === capabilityId)
    const created: MemoryAssociation[] = []

    for (let i = 0; i < capEntries.length; i++) {
      for (let j = i + 1; j < capEntries.length; j++) {
        const assoc = await this.createAssociation(
          capEntries[i].id,
          capEntries[j].id,
          "same_capability",
          0.6,
          { capabilityId },
        )
        created.push(assoc)
      }
    }
    return created
  },

  async findByTemporal(entries: MemoryEntryBase[], sessionId: string, windowMs: number): Promise<MemoryAssociation[]> {
    const sessionEntries = entries
      .filter((e) => e.sessionId === sessionId)
      .sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime())
    const created: MemoryAssociation[] = []

    for (let i = 0; i < sessionEntries.length; i++) {
      const timeI = new Date(sessionEntries[i].createdAt).getTime()
      for (let j = i + 1; j < sessionEntries.length; j++) {
        const timeJ = new Date(sessionEntries[j].createdAt).getTime()
        if (timeJ - timeI <= windowMs) {
          const assoc = await this.createAssociation(
            sessionEntries[i].id,
            sessionEntries[j].id,
            "temporal",
            0.5,
            { windowMs: String(windowMs) },
          )
          created.push(assoc)
        } else {
          break
        }
      }
    }
    return created
  },

  async findBySemanticCategory(entries: MemoryEntryBase[], category: string): Promise<MemoryAssociation[]> {
    const catEntries = entries.filter((e) => (e.metadata["category"] ?? "") === category)
    const created: MemoryAssociation[] = []

    for (let i = 0; i < catEntries.length; i++) {
      for (let j = i + 1; j < catEntries.length; j++) {
        const assoc = await this.createAssociation(
          catEntries[i].id,
          catEntries[j].id,
          "semantic_category",
          0.6,
          { category },
        )
        created.push(assoc)
      }
    }
    return created
  },

  async findBySequential(entries: MemoryEntryBase[], sessionId: string): Promise<MemoryAssociation[]> {
    const sessionEntries = entries
      .filter((e) => e.sessionId === sessionId)
      .sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime())
    const created: MemoryAssociation[] = []

    for (let i = 0; i < sessionEntries.length - 1; i++) {
      const assoc = await this.createAssociation(
        sessionEntries[i].id,
        sessionEntries[i + 1].id,
        "sequential",
        0.4,
        { order: String(i) },
      )
      created.push(assoc)
    }
    return created
  },

  async getAssociationsByEntry(entryId: string): Promise<MemoryAssociation[]> {
    const client = RedisClient.getClient()
    if (!client) return []
    const ids = new Set<string>()
    const sourceIds = await client.smembers(`${SOURCE_INDEX_KEY}:${entryId}`)
    const targetIds = await client.smembers(`${TARGET_INDEX_KEY}:${entryId}`)
    sourceIds.forEach((id) => ids.add(id))
    targetIds.forEach((id) => ids.add(id))

    const associations: MemoryAssociation[] = []
    for (const id of ids) {
      const data = await client.hgetall(`${ASSOC_KEY}:${id}`)
      if (data && Object.keys(data).length > 0) {
        associations.push(deserializeAssociation(data))
      }
    }
    return associations
  },

  async getAssociationsByType(type: AssociationType): Promise<MemoryAssociation[]> {
    const client = RedisClient.getClient()
    if (!client) return []
    const ids = await client.smembers(`${TYPE_INDEX_KEY}:${type}`)
    const associations: MemoryAssociation[] = []
    for (const id of ids) {
      const data = await client.hgetall(`${ASSOC_KEY}:${id}`)
      if (data && Object.keys(data).length > 0) {
        associations.push(deserializeAssociation(data))
      }
    }
    return associations
  },

  async getAssociationsBySession(entryIds: string[]): Promise<MemoryAssociation[]> {
    const idSet = new Set(entryIds)
    const client = RedisClient.getClient()
    if (!client) return []
    const assocIds = new Set<string>()
    for (const entryId of entryIds) {
      const sourceIds = await client.smembers(`${SOURCE_INDEX_KEY}:${entryId}`)
      const targetIds = await client.smembers(`${TARGET_INDEX_KEY}:${entryId}`)
      sourceIds.forEach((id) => assocIds.add(id))
      targetIds.forEach((id) => assocIds.add(id))
    }

    const associations: MemoryAssociation[] = []
    for (const id of assocIds) {
      const data = await client.hgetall(`${ASSOC_KEY}:${id}`)
      if (!data || Object.keys(data).length === 0) continue
      const assoc = deserializeAssociation(data)
      if (idSet.has(assoc.sourceId) || idSet.has(assoc.targetId)) {
        associations.push(assoc)
      }
    }
    return associations
  },

  async count(): Promise<number> {
    const client = RedisClient.getClient()
    if (!client) return 0
    const keys = await client.keys(`${ASSOC_KEY}:*`)
    return keys.length
  },

  async clearAll(): Promise<void> {
    const client = RedisClient.getClient()
    if (!client) return
    await RedisClient.flushPrefix("assoc:")
  },
}
