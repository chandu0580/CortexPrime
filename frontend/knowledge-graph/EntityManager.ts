import type { KnowledgeEntity, EntityCategory, EntityStatus } from "./types"
import { generateId } from "@/worker-framework/shared"
import { Neo4jClient } from "./Neo4jClient"

function serializeEntityProps(entity: KnowledgeEntity): Record<string, unknown> {
  return {
    entityId: entity.id,
    name: entity.name,
    entityType: entity.type,
    category: entity.category,
    status: entity.status,
    description: entity.description,
    properties: JSON.stringify(entity.properties),
    tags: JSON.stringify(entity.tags),
    source: entity.source,
    confidence: entity.confidence,
    aliases: JSON.stringify(entity.aliases),
    createdAt: entity.createdAt,
    updatedAt: entity.updatedAt,
  }
}

function deserializeEntity(record: Record<string, unknown>): KnowledgeEntity {
  return {
    id: record.entityId as string,
    name: record.name as string,
    type: record.entityType as string,
    category: record.category as EntityCategory,
    status: record.status as EntityStatus,
    description: record.description as string,
    properties: JSON.parse((record.properties as string) || "{}"),
    tags: JSON.parse((record.tags as string) || "[]"),
    source: record.source as string,
    confidence: record.confidence as number,
    aliases: JSON.parse((record.aliases as string) || "[]"),
    createdAt: record.createdAt as string,
    updatedAt: record.updatedAt as string,
  }
}

export const EntityManager = {
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
    const now = new Date().toISOString()
    const entity: KnowledgeEntity = {
      id: generateId("kg-entity"),
      name,
      type,
      category,
      status: "active",
      description,
      properties: properties ?? {},
      tags: tags ?? [],
      source: source ?? "system",
      confidence: confidence ?? 1.0,
      aliases: aliases ?? [],
      createdAt: now,
      updatedAt: now,
    }

    const client = Neo4jClient.getDriver()
    if (client) {
      await Neo4jClient.run(
        `CREATE (e:Entity $props) RETURN e`,
        { props: serializeEntityProps(entity) },
      )
    }

    return { ...entity }
  },

  async updateEntity(entityId: string, updates: Partial<Omit<KnowledgeEntity, "id" | "createdAt">>): Promise<KnowledgeEntity> {
    const existing = await this.findEntity(entityId)
    if (!existing) throw new Error(`Entity ${entityId} not found`)

    const updated = { ...existing, ...updates, updatedAt: new Date().toISOString() }

    const client = Neo4jClient.getDriver()
    if (client) {
      await Neo4jClient.run(
        `MATCH (e:Entity {entityId: $entityId})
         SET e += $props
         RETURN e`,
        { entityId, props: serializeEntityProps(updated) },
      )
    }

    return updated
  },

  async removeEntity(entityId: string): Promise<void> {
    const entity = await this.findEntity(entityId)
    if (!entity) throw new Error(`Entity ${entityId} not found`)

    const client = Neo4jClient.getDriver()
    if (client) {
      await Neo4jClient.run(
        `MATCH (e:Entity {entityId: $entityId})
         SET e.status = 'archived', e.updatedAt = $updatedAt
         RETURN e`,
        { entityId, updatedAt: new Date().toISOString() },
      )
    }
  },

  async findEntity(entityId: string): Promise<KnowledgeEntity | null> {
    const client = Neo4jClient.getDriver()
    if (!client) return null

    const result = await Neo4jClient.run(
      `MATCH (e:Entity {entityId: $entityId})
       WHERE e.status <> 'archived'
       RETURN e`,
      { entityId },
    )

    if (result.records.length === 0) return null
    const record = result.records[0].get("e").properties
    return deserializeEntity(record)
  },

  async queryEntities(query: { field?: string; value?: string; category?: EntityCategory; tag?: string; name?: string }): Promise<KnowledgeEntity[]> {
    const client = Neo4jClient.getDriver()
    if (!client) return []

    const conditions: string[] = ["e.status <> 'archived'"]
    const params: Record<string, unknown> = {}

    if (query.category) {
      conditions.push("e.category = $category")
      params.category = query.category
    }
    if (query.tag) {
      conditions.push("ANY(t IN split(e.tags, ',') WHERE t = $tag)")
      params.tag = query.tag
    }
    if (query.name) {
      conditions.push("(e.name CONTAINS $name OR ANY(a IN split(e.aliases, ',') WHERE a CONTAINS $name))")
      params.name = query.name.toLowerCase()
    }
    if (query.field && query.value) {
      conditions.push(`e.${query.field} CONTAINS $value`)
      params.value = query.value.toLowerCase()
    }

    const whereClause = conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : ""

    const result = await Neo4jClient.run(
      `MATCH (e:Entity) ${whereClause} RETURN e`,
      params,
    )

    return result.records.map((record) => deserializeEntity(record.get("e").properties))
  },

  async categorize(entityId: string, category: EntityCategory): Promise<void> {
    const entity = await this.findEntity(entityId)
    if (!entity) throw new Error(`Entity ${entityId} not found`)

    const client = Neo4jClient.getDriver()
    if (client) {
      await Neo4jClient.run(
        `MATCH (e:Entity {entityId: $entityId})
         SET e.category = $category, e.updatedAt = $updatedAt`,
        { entityId, category, updatedAt: new Date().toISOString() },
      )
    }
  },

  async mergeEntities(targetId: string, sourceId: string): Promise<KnowledgeEntity> {
    const target = await this.findEntity(targetId)
    const source = await this.findEntity(sourceId)
    if (!target) throw new Error(`Target entity ${targetId} not found`)
    if (!source) throw new Error(`Source entity ${sourceId} not found`)

    const client = Neo4jClient.getDriver()
    if (client) {
      await Neo4jClient.run(
        `MATCH (s:Entity {entityId: $sourceId})
         SET s.status = 'merged', s.updatedAt = $updatedAt`,
        { sourceId, updatedAt: new Date().toISOString() },
      )

      const merged = {
        ...target,
        aliases: [...new Set([...target.aliases, ...source.aliases, source.name])],
        tags: [...new Set([...target.tags, ...source.tags])],
        properties: { ...target.properties, ...source.properties, mergedFrom: sourceId },
        updatedAt: new Date().toISOString(),
      }

      await Neo4jClient.run(
        `MATCH (t:Entity {entityId: $targetId})
         SET t += $props`,
        { targetId, props: serializeEntityProps(merged) },
      )

      return merged
    }

    return target
  },

  async getEntityCount(): Promise<number> {
    const client = Neo4jClient.getDriver()
    if (!client) return 0

    const result = await Neo4jClient.run(
      `MATCH (e:Entity) WHERE e.status <> 'archived' RETURN count(e) AS count`,
    )

    return result.records[0].get("count").toNumber()
  },

  async getActiveEntities(): Promise<KnowledgeEntity[]> {
    const client = Neo4jClient.getDriver()
    if (!client) return []

    const result = await Neo4jClient.run(
      `MATCH (e:Entity) WHERE e.status = 'active' RETURN e`,
    )

    return result.records.map((record) => deserializeEntity(record.get("e").properties))
  },

  async findDuplicates(): Promise<string[][]> {
    const client = Neo4jClient.getDriver()
    if (!client) return []

    const result = await Neo4jClient.run(
      `MATCH (e:Entity)
       WHERE e.status = 'active'
       WITH e.entityType AS entityType, e.name AS name, collect(e.entityId) AS ids
       WHERE size(ids) > 1
       RETURN ids`,
    )

    return result.records.map((record) => record.get("ids"))
  },

  async getAll(): Promise<KnowledgeEntity[]> {
    const client = Neo4jClient.getDriver()
    if (!client) return []

    const result = await Neo4jClient.run(
      `MATCH (e:Entity) RETURN e`,
    )

    return result.records.map((record) => deserializeEntity(record.get("e").properties))
  },

  async clear(): Promise<void> {
    const client = Neo4jClient.getDriver()
    if (!client) return

    await Neo4jClient.run(`MATCH (e:Entity) DETACH DELETE e`)
  },
}
