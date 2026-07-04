import type { KnowledgeInference, KnowledgeRelationship, RelationshipType, GraphNode } from "./types"
import { EntityManager } from "./EntityManager"
import { RelationshipManager } from "./RelationshipManager"
import { GraphManager } from "./GraphManager"
import { generateId } from "@/worker-framework/shared"
import { Neo4jClient } from "./Neo4jClient"

const TRANSITIVE_TYPES: RelationshipType[] = ["depends_on", "part_of", "composed_of", "causes"]
const SYMMETRIC_TYPES: RelationshipType[] = ["same_as", "equivalent_to", "relates_to"]

export const GraphInferenceEngine = {
  async inferRelationships(): Promise<KnowledgeInference[]> {
    const inferred: KnowledgeInference[] = []
    const allRels = await RelationshipManager.getAll()

    for (const rel of allRels) {
      if (TRANSITIVE_TYPES.includes(rel.type)) {
        const transitive = await this.inferTransitive(rel, allRels)
        inferred.push(...transitive)
      }
      if (SYMMETRIC_TYPES.includes(rel.type) && !rel.bidirectional) {
        const symmetric = await this.inferSymmetric(rel)
        inferred.push(...symmetric)
      }
    }

    const client = Neo4jClient.getDriver()
    if (client && inferred.length > 0) {
      for (const inference of inferred) {
        await Neo4jClient.run(
          `CREATE (i:Inference {
            inferenceId: $inferenceId,
            inferenceType: $inferenceType,
            sourceRelationships: $sourceRelationships,
            inferredRelationship: $inferredRelationship,
            confidence: $confidence,
            rationale: $rationale,
            createdAt: $createdAt
          }) RETURN i`,
          {
            inferenceId: inference.id,
            inferenceType: inference.type,
            sourceRelationships: JSON.stringify(inference.sourceRelationships),
            inferredRelationship: JSON.stringify(inference.inferredRelationship),
            confidence: inference.confidence,
            rationale: inference.rationale,
            createdAt: inference.createdAt,
          },
        )
      }
    }

    return inferred
  },

  async inferTransitive(
    relationship: KnowledgeRelationship,
    allRelationships: KnowledgeRelationship[],
  ): Promise<KnowledgeInference[]> {
    const inferred: KnowledgeInference[] = []

    for (const other of allRelationships) {
      if (other.id === relationship.id) continue
      if (other.type !== relationship.type) continue

      if (other.sourceId === relationship.targetId) {
        const existing = allRelationships.find(
          (r) => r.sourceId === relationship.sourceId && r.targetId === other.targetId && r.type === relationship.type,
        )
        if (!existing) {
          const newRel = await RelationshipManager.createRelationship(
            relationship.sourceId,
            other.targetId,
            relationship.type,
            Math.min(relationship.weight, other.weight),
            Math.min(relationship.confidence, other.confidence),
            { inferred: "true", via: relationship.id, andVia: other.id },
          )

          const inference: KnowledgeInference = {
            id: generateId("kg-inference"),
            type: "transitive",
            sourceRelationships: [relationship.id, other.id],
            inferredRelationship: newRel,
            confidence: Math.min(relationship.confidence, other.confidence) * 0.9,
            rationale: `${relationship.sourceId} -> ${relationship.targetId} -> ${other.targetId} via transitive ${relationship.type}`,
            createdAt: new Date().toISOString(),
          }
          inferred.push(inference)
        }
      }
    }

    return inferred
  },

  async inferSymmetric(relationship: KnowledgeRelationship): Promise<KnowledgeInference[]> {
    const existing = await RelationshipManager.findRelationships(relationship.targetId)
    const hasReverse = existing.some(
      (r) => r.sourceId === relationship.targetId && r.targetId === relationship.sourceId && r.type === relationship.type,
    )

    if (!hasReverse) {
      const reverseRel = await RelationshipManager.createRelationship(
        relationship.targetId,
        relationship.sourceId,
        relationship.type,
        relationship.weight,
        relationship.confidence,
        { ...relationship.properties, inferred: "true", symmetricOf: relationship.id },
        true,
      )

      const inference: KnowledgeInference = {
        id: generateId("kg-inference"),
        type: "symmetric",
        sourceRelationships: [relationship.id],
        inferredRelationship: reverseRel,
        confidence: relationship.confidence * 0.95,
        rationale: `Inferred reverse relationship for symmetric type ${relationship.type}`,
        createdAt: new Date().toISOString(),
      }
      return [inference]
    }

    return []
  },

  async inferClusters(): Promise<Array<{ label: string; entityIds: string[]; centralEntityId: string | null }>> {
    const components = await GraphManager.findConnectedComponents()
    const clusters: Array<{ label: string; entityIds: string[]; centralEntityId: string | null }> = []

    for (const component of components) {
      const entityIds: string[] = []
      let maxDegree = 0
      let centralNodeId: string | null = null

      for (const nodeId of component) {
        const node = await GraphManager.getNode(nodeId)
        if (!node) continue
        entityIds.push(node.entityId)

        const edges = await GraphManager.getEdgesByNode(nodeId)
        if (edges.length > maxDegree) {
          maxDegree = edges.length
          centralNodeId = node.entityId
        }
      }

      if (entityIds.length > 0) {
        clusters.push({
          label: `Cluster ${clusters.length + 1} (${entityIds.length} entities)`,
          entityIds,
          centralEntityId: centralNodeId,
        })
      }
    }

    return clusters
  },

  async inferCategories(): Promise<Array<{ category: string; entityIds: string[] }>> {
    const entities = await EntityManager.getActiveEntities()
    const categories = new Map<string, string[]>()

    for (const entity of entities) {
      const cat = entity.category
      if (!categories.has(cat)) categories.set(cat, [])
      categories.get(cat)!.push(entity.id)
    }

    return Array.from(categories.entries()).map(([category, entityIds]) => ({ category, entityIds }))
  },

  async detectCycles(): Promise<GraphNode[][]> {
    const client = Neo4jClient.getDriver()
    if (!client) return []

    const result = await Neo4jClient.run(
      `MATCH (n:GraphNode)
       CALL apoc.path.cyclePath(n, 10, 'GRAPH_EDGE') YIELD path
       RETURN nodes(path) AS ns`,
    )

    const cycles: GraphNode[][] = []
    for (const record of result.records) {
      const ns = record.get("ns") as Array<Record<string, unknown>>
      const nodes = ns.map((n) => ({
        id: n.nodeId as string,
        entityId: n.entityId as string,
        label: n.label as string,
        category: n.category as GraphNode["category"],
        properties: JSON.parse((n.properties as string) || "{}"),
      }))
      if (nodes.length >= 3) cycles.push(nodes)
    }

    return cycles
  },

  async detectRedundancy(): Promise<KnowledgeRelationship[]> {
    const allRels = await RelationshipManager.getAll()
    const redundant: KnowledgeRelationship[] = []

    for (let i = 0; i < allRels.length; i++) {
      for (let j = i + 1; j < allRels.length; j++) {
        const a = allRels[i]
        const b = allRels[j]

        if (a.sourceId === b.sourceId && a.targetId === b.targetId && a.type === b.type) {
          if (!redundant.some((r) => r.id === b.id)) redundant.push(b)
        }

        if (a.sourceId === b.targetId && a.targetId === b.sourceId && a.type === b.type && a.bidirectional && b.bidirectional) {
          if (!redundant.some((r) => r.id === b.id)) redundant.push(b)
        }
      }
    }

    return redundant
  },

  async getInferenceCount(): Promise<number> {
    const client = Neo4jClient.getDriver()
    if (!client) return 0

    const result = await Neo4jClient.run(
      `MATCH (i:Inference) RETURN count(i) AS count`,
    )

    return result.records[0].get("count").toNumber()
  },

  async clear(): Promise<void> {
    const client = Neo4jClient.getDriver()
    if (!client) return

    await Neo4jClient.run(`MATCH (i:Inference) DELETE i`)
  },
}
