import type { GraphNode, GraphEdge, KnowledgeEntity, KnowledgeRelationship, EntityCategory, RelationshipType } from "./types"
import { generateId } from "@/worker-framework/shared"
import { Neo4jClient } from "./Neo4jClient"

function deserializeNode(record: Record<string, unknown>): GraphNode {
  return {
    id: record.nodeId as string,
    entityId: record.entityId as string,
    label: record.label as string,
    category: record.category as EntityCategory,
    properties: JSON.parse((record.properties as string) || "{}"),
  }
}

function deserializeEdge(record: Record<string, unknown>): GraphEdge {
  return {
    id: record.edgeId as string,
    sourceNodeId: record.sourceNodeId as string,
    targetNodeId: record.targetNodeId as string,
    relationshipId: record.relationshipId as string,
    type: record.relType as RelationshipType,
    weight: record.weight as number,
  }
}

export const GraphManager = {
  async addNode(entity: KnowledgeEntity): Promise<GraphNode> {
    const client = Neo4jClient.getDriver()
    if (!client) {
      return {
        id: generateId("kg-node"),
        entityId: entity.id,
        label: entity.name,
        category: entity.category,
        properties: Object.fromEntries(
          Object.entries(entity.properties).map(([k, v]) => [k, String(v)]),
        ),
      }
    }

    const existing = await this.getNodeByEntityId(entity.id)
    if (existing) return existing

    const node: GraphNode = {
      id: generateId("kg-node"),
      entityId: entity.id,
      label: entity.name,
      category: entity.category,
      properties: Object.fromEntries(
        Object.entries(entity.properties).map(([k, v]) => [k, String(v)]),
      ),
    }

    await Neo4jClient.run(
      `CREATE (n:GraphNode {
        nodeId: $nodeId,
        entityId: $entityId,
        label: $label,
        category: $category,
        properties: $properties
      }) RETURN n`,
      {
        nodeId: node.id,
        entityId: node.entityId,
        label: node.label,
        category: node.category,
        properties: JSON.stringify(node.properties),
      },
    )

    return { ...node }
  },

  async removeNode(nodeId: string): Promise<void> {
    const client = Neo4jClient.getDriver()
    if (!client) return

    await Neo4jClient.run(
      `MATCH (n:GraphNode {nodeId: $nodeId})
       DETACH DELETE n`,
      { nodeId },
    )
  },

  async addEdge(relationship: KnowledgeRelationship): Promise<GraphEdge> {
    const client = Neo4jClient.getDriver()
    if (!client) {
      return {
        id: generateId("kg-edge"),
        sourceNodeId: "",
        targetNodeId: "",
        relationshipId: relationship.id,
        type: relationship.type,
        weight: relationship.weight,
      }
    }

    const sourceNode = await this.getNodeByEntityId(relationship.sourceId)
    const targetNode = await this.getNodeByEntityId(relationship.targetId)
    if (!sourceNode) throw new Error(`No graph node for entity ${relationship.sourceId}`)
    if (!targetNode) throw new Error(`No graph node for entity ${relationship.targetId}`)

    const edgeId = generateId("kg-edge")

    await Neo4jClient.run(
      `MATCH (s:GraphNode {nodeId: $sourceNodeId})
       MATCH (t:GraphNode {nodeId: $targetNodeId})
       CREATE (s)-[e:GRAPH_EDGE {
        edgeId: $edgeId,
        sourceNodeId: $sourceNodeId,
        targetNodeId: $targetNodeId,
        relationshipId: $relationshipId,
        relType: $relType,
        weight: $weight
       }]->(t)
       RETURN e`,
      {
        edgeId,
        sourceNodeId: sourceNode.id,
        targetNodeId: targetNode.id,
        relationshipId: relationship.id,
        relType: relationship.type,
        weight: relationship.weight,
      },
    )

    if (relationship.bidirectional) {
      const reverseEdgeId = generateId("kg-edge")
      await Neo4jClient.run(
        `MATCH (s:GraphNode {nodeId: $sourceNodeId})
         MATCH (t:GraphNode {nodeId: $targetNodeId})
         CREATE (t)-[e:GRAPH_EDGE {
          edgeId: $edgeId,
          sourceNodeId: $targetNodeId,
          targetNodeId: $sourceNodeId,
          relationshipId: $relationshipId,
          relType: $relType,
          weight: $weight
         }]->(s)
         RETURN e`,
        {
          edgeId: reverseEdgeId,
          sourceNodeId: sourceNode.id,
          targetNodeId: targetNode.id,
          relationshipId: relationship.id,
          relType: relationship.type,
          weight: relationship.weight,
        },
      )
    }

    const edge: GraphEdge = {
      id: edgeId,
      sourceNodeId: sourceNode.id,
      targetNodeId: targetNode.id,
      relationshipId: relationship.id,
      type: relationship.type,
      weight: relationship.weight,
    }

    return { ...edge }
  },

  async removeEdge(edgeId: string): Promise<void> {
    const client = Neo4jClient.getDriver()
    if (!client) return

    await Neo4jClient.run(
      `MATCH ()-[e:GRAPH_EDGE {edgeId: $edgeId}]-()
       DELETE e`,
      { edgeId },
    )
  },

  async getNode(nodeId: string): Promise<GraphNode | null> {
    const client = Neo4jClient.getDriver()
    if (!client) return null

    const result = await Neo4jClient.run(
      `MATCH (n:GraphNode {nodeId: $nodeId}) RETURN n`,
      { nodeId },
    )

    if (result.records.length === 0) return null
    return deserializeNode(result.records[0].get("n").properties)
  },

  async getEdge(edgeId: string): Promise<GraphEdge | null> {
    const client = Neo4jClient.getDriver()
    if (!client) return null

    const result = await Neo4jClient.run(
      `MATCH ()-[e:GRAPH_EDGE {edgeId: $edgeId}]-() RETURN e`,
      { edgeId },
    )

    if (result.records.length === 0) return null
    return deserializeEdge(result.records[0].get("e").properties)
  },

  async getNodeByEntityId(entityId: string): Promise<GraphNode | null> {
    const client = Neo4jClient.getDriver()
    if (!client) return null

    const result = await Neo4jClient.run(
      `MATCH (n:GraphNode {entityId: $entityId}) RETURN n`,
      { entityId },
    )

    if (result.records.length === 0) return null
    return deserializeNode(result.records[0].get("n").properties)
  },

  async getEdgesByNode(nodeId: string): Promise<GraphEdge[]> {
    const client = Neo4jClient.getDriver()
    if (!client) return []

    const result = await Neo4jClient.run(
      `MATCH (n:GraphNode {nodeId: $nodeId})-[e:GRAPH_EDGE]-(m:GraphNode)
       RETURN e`,
      { nodeId },
    )

    return result.records.map((record) => deserializeEdge(record.get("e").properties))
  },

  async getNeighborNodes(nodeId: string): Promise<GraphNode[]> {
    const client = Neo4jClient.getDriver()
    if (!client) return []

    const result = await Neo4jClient.run(
      `MATCH (n:GraphNode {nodeId: $nodeId})-[e:GRAPH_EDGE]-(m:GraphNode)
       RETURN DISTINCT m`,
      { nodeId },
    )

    return result.records.map((record) => deserializeNode(record.get("m").properties))
  },

  async countNodes(): Promise<number> {
    const client = Neo4jClient.getDriver()
    if (!client) return 0

    const result = await Neo4jClient.run(
      `MATCH (n:GraphNode) RETURN count(n) AS count`,
    )

    return result.records[0].get("count").toNumber()
  },

  async countEdges(): Promise<number> {
    const client = Neo4jClient.getDriver()
    if (!client) return 0

    const result = await Neo4jClient.run(
      `MATCH ()-[e:GRAPH_EDGE]-() RETURN count(e) AS count`,
    )

    return result.records[0].get("count").toNumber()
  },

  async getGraphDensity(): Promise<number> {
    const n = await this.countNodes()
    if (n <= 1) return 0
    const e = await this.countEdges()
    return e / ((n * (n - 1)) / 2)
  },

  async findConnectedComponents(): Promise<string[][]> {
    const client = Neo4jClient.getDriver()
    if (!client) return []

    const result = await Neo4jClient.run(
      `MATCH (n:GraphNode)
       CALL {
         WITH n
         MATCH path = (n)-[:GRAPH_EDGE*0..]-(m:GraphNode)
         WITH collect(DISTINCT m.nodeId) AS componentIds
         RETURN componentIds
       }
       RETURN DISTINCT componentIds`,
    )

    return result.records.map((record) => record.get("componentIds"))
  },

  async findOrphanNodes(): Promise<string[]> {
    const client = Neo4jClient.getDriver()
    if (!client) return []

    const result = await Neo4jClient.run(
      `MATCH (n:GraphNode)
       WHERE NOT (n)-[:GRAPH_EDGE]-()
       RETURN n.nodeId AS nodeId`,
    )

    return result.records.map((record) => record.get("nodeId"))
  },

  async getAllNodes(): Promise<GraphNode[]> {
    const client = Neo4jClient.getDriver()
    if (!client) return []

    const result = await Neo4jClient.run(
      `MATCH (n:GraphNode) RETURN n`,
    )

    return result.records.map((record) => deserializeNode(record.get("n").properties))
  },

  async getAllEdges(): Promise<GraphEdge[]> {
    const client = Neo4jClient.getDriver()
    if (!client) return []

    const result = await Neo4jClient.run(
      `MATCH ()-[e:GRAPH_EDGE]-() RETURN e`,
    )

    return result.records.map((record) => deserializeEdge(record.get("e").properties))
  },

  async clear(): Promise<void> {
    const client = Neo4jClient.getDriver()
    if (!client) return

    await Neo4jClient.run(`MATCH (n:GraphNode) DETACH DELETE n`)
  },
}
