import type { KnowledgeRelationship, RelationshipType, EntityReference } from "./types"
import { EntityManager } from "./EntityManager"
import { generateId } from "@/worker-framework/shared"
import { Neo4jClient } from "./Neo4jClient"

function serializeRelProps(rel: KnowledgeRelationship): Record<string, unknown> {
  return {
    relationshipId: rel.id,
    sourceId: rel.sourceId,
    targetId: rel.targetId,
    relType: rel.type,
    weight: rel.weight,
    confidence: rel.confidence,
    properties: JSON.stringify(rel.properties),
    bidirectional: rel.bidirectional,
    createdAt: rel.createdAt,
    updatedAt: rel.updatedAt,
  }
}

function deserializeRelationship(record: Record<string, unknown>): KnowledgeRelationship {
  return {
    id: record.relationshipId as string,
    sourceId: record.sourceId as string,
    targetId: record.targetId as string,
    type: record.relType as RelationshipType,
    weight: record.weight as number,
    confidence: record.confidence as number,
    properties: JSON.parse((record.properties as string) || "{}"),
    bidirectional: record.bidirectional as boolean,
    createdAt: record.createdAt as string,
    updatedAt: record.updatedAt as string,
  }
}

export const RelationshipManager = {
  async createRelationship(
    sourceId: string,
    targetId: string,
    type: RelationshipType,
    weight: number = 1.0,
    confidence?: number,
    properties?: Record<string, string>,
    bidirectional?: boolean,
  ): Promise<KnowledgeRelationship> {
    const source = await EntityManager.findEntity(sourceId)
    const target = await EntityManager.findEntity(targetId)
    if (!source) throw new Error(`Source entity ${sourceId} not found`)
    if (!target) throw new Error(`Target entity ${targetId} not found`)

    const now = new Date().toISOString()
    const relationship: KnowledgeRelationship = {
      id: generateId("kg-relationship"),
      sourceId,
      targetId,
      type,
      weight: Math.min(Math.max(weight, 0), 1),
      confidence: confidence ?? Math.min(source.confidence, target.confidence),
      properties: properties ?? {},
      bidirectional: bidirectional ?? false,
      createdAt: now,
      updatedAt: now,
    }

    const client = Neo4jClient.getDriver()
    if (client) {
      await Neo4jClient.run(
        `MATCH (s:Entity {entityId: $sourceId})
         MATCH (t:Entity {entityId: $targetId})
         CREATE (s)-[r:RELATES_TO $props]->(t)
         RETURN r`,
        { sourceId, targetId, props: serializeRelProps(relationship) },
      )

      if (relationship.bidirectional) {
        await Neo4jClient.run(
          `MATCH (s:Entity {entityId: $sourceId})
           MATCH (t:Entity {entityId: $targetId})
           CREATE (t)-[r:RELATES_TO $props]->(s)
           RETURN r`,
          {
            sourceId, targetId,
            props: { ...serializeRelProps(relationship), bidirectional: true },
          },
        )
      }
    }

    return { ...relationship }
  },

  async removeRelationship(relationshipId: string): Promise<void> {
    const client = Neo4jClient.getDriver()
    if (!client) return

    await Neo4jClient.run(
      `MATCH ()-[r:RELATES_TO {relationshipId: $relationshipId}]-()
       DELETE r`,
      { relationshipId },
    )
  },

  async updateRelationship(relationshipId: string, updates: Partial<Omit<KnowledgeRelationship, "id" | "createdAt">>): Promise<KnowledgeRelationship> {
    const client = Neo4jClient.getDriver()
    if (!client) throw new Error("Neo4j not connected")

    const result = await Neo4jClient.run(
      `MATCH ()-[r:RELATES_TO {relationshipId: $relationshipId}]-()
       RETURN r`,
      { relationshipId },
    )

    if (result.records.length === 0) throw new Error(`Relationship ${relationshipId} not found`)

    const existing = deserializeRelationship(result.records[0].get("r").properties)
    const updated = { ...existing, ...updates, updatedAt: new Date().toISOString() }

    await Neo4jClient.run(
      `MATCH ()-[r:RELATES_TO {relationshipId: $relationshipId}]-()
       SET r += $props`,
      { relationshipId, props: serializeRelProps(updated) },
    )

    return updated
  },

  async findRelationships(entityId?: string, type?: RelationshipType): Promise<KnowledgeRelationship[]> {
    const client = Neo4jClient.getDriver()
    if (!client) return []

    let query = `MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity)`
    const conditions: string[] = []
    const params: Record<string, unknown> = {}

    if (entityId) {
      conditions.push("(a.entityId = $entityId OR b.entityId = $entityId)")
      params.entityId = entityId
    }
    if (type) {
      conditions.push("r.relType = $type")
      params.type = type
    }

    if (conditions.length > 0) {
      query += ` WHERE ${conditions.join(" AND ")}`
    }

    query += ` RETURN r`

    const result = await Neo4jClient.run(query, params)
    return result.records.map((record) => deserializeRelationship(record.get("r").properties))
  },

  async queryNeighbors(entityId: string, maxDepth: number = 1): Promise<EntityReference[]> {
    const client = Neo4jClient.getDriver()
    if (!client) return []

    const result = await Neo4jClient.run(
      `MATCH (center:Entity {entityId: $entityId})
       MATCH (center)-[r:RELATES_TO*1..${maxDepth}]-(neighbor:Entity)
       RETURN DISTINCT neighbor.entityId AS entityId, neighbor.name AS name,
              neighbor.category AS category, type(r[0]) AS relType`,
      { entityId },
    )

    return result.records.map((record) => ({
      entityId: record.get("entityId"),
      name: record.get("name"),
      category: record.get("category"),
      relationship: record.get("relType") as RelationshipType,
    }))
  },

  async getRelationshipsBySource(sourceId: string): Promise<KnowledgeRelationship[]> {
    const client = Neo4jClient.getDriver()
    if (!client) return []

    const result = await Neo4jClient.run(
      `MATCH (s:Entity {entityId: $sourceId})-[r:RELATES_TO]->(t:Entity)
       RETURN r`,
      { sourceId },
    )

    return result.records.map((record) => deserializeRelationship(record.get("r").properties))
  },

  async getRelationshipsByTarget(targetId: string): Promise<KnowledgeRelationship[]> {
    const client = Neo4jClient.getDriver()
    if (!client) return []

    const result = await Neo4jClient.run(
      `MATCH (s:Entity)-[r:RELATES_TO]->(t:Entity {entityId: $targetId})
       RETURN r`,
      { targetId },
    )

    return result.records.map((record) => deserializeRelationship(record.get("r").properties))
  },

  async countByType(): Promise<Record<string, number>> {
    const client = Neo4jClient.getDriver()
    if (!client) return {}

    const result = await Neo4jClient.run(
      `MATCH ()-[r:RELATES_TO]-()
       RETURN r.relType AS type, count(r) AS count`,
    )

    const counts: Record<string, number> = {}
    for (const record of result.records) {
      counts[record.get("type")] = record.get("count").toNumber()
    }
    return counts
  },

  async getRelationshipCount(): Promise<number> {
    const client = Neo4jClient.getDriver()
    if (!client) return 0

    const result = await Neo4jClient.run(
      `MATCH ()-[r:RELATES_TO]-() RETURN count(r) AS count`,
    )

    return result.records[0].get("count").toNumber()
  },

  async getAll(): Promise<KnowledgeRelationship[]> {
    const client = Neo4jClient.getDriver()
    if (!client) return []

    const result = await Neo4jClient.run(
      `MATCH ()-[r:RELATES_TO]-() RETURN r`,
    )

    return result.records.map((record) => deserializeRelationship(record.get("r").properties))
  },

  async clear(): Promise<void> {
    const client = Neo4jClient.getDriver()
    if (!client) return

    await Neo4jClient.run(`MATCH ()-[r:RELATES_TO]-() DELETE r`)
  },
}
