import type { GraphPath, GraphNode, GraphEdge, GraphNeighborhood, EntityCategory, RelationshipType } from "./types"
import { GraphManager } from "./GraphManager"
import { Neo4jClient } from "./Neo4jClient"

function deserializePathNode(record: Record<string, unknown>): GraphNode {
  return {
    id: record.nodeId as string,
    entityId: record.entityId as string,
    label: record.label as string,
    category: record.category as EntityCategory,
    properties: JSON.parse((record.properties as string) || "{}"),
  }
}

function deserializePathEdge(record: Record<string, unknown>): GraphEdge {
  return {
    id: record.edgeId as string,
    sourceNodeId: record.sourceNodeId as string,
    targetNodeId: record.targetNodeId as string,
    relationshipId: record.relationshipId as string,
    type: record.relType as RelationshipType,
    weight: record.weight as number,
  }
}

export const GraphTraversalEngine = {
  async bfs(startNodeId: string, maxDepth: number = 5): Promise<GraphPath[]> {
    const client = Neo4jClient.getDriver()
    if (!client) return []

    const result = await Neo4jClient.run(
      `MATCH (start:GraphNode {nodeId: $startNodeId})
       CALL apoc.path.spanningTree(start, {}, {}, $maxDepth, '') YIELD path
       WITH path, nodes(path) AS ns, relationships(path) AS rs
       RETURN ns, rs`,
      { startNodeId, maxDepth },
    )

    const paths: GraphPath[] = []
    for (const record of result.records) {
      const ns = record.get("ns") as Array<Record<string, unknown>>
      const rs = record.get("rs") as Array<Record<string, unknown>>

      const nodes = ns.map((n) => deserializePathNode(n.properties as Record<string, unknown>))
      const edges = rs.map((r) => deserializePathEdge(r.properties as Record<string, unknown>))

      paths.push({
        nodes,
        edges,
        totalWeight: edges.reduce((sum, e) => sum + e.weight, 0),
        nodeCount: nodes.length,
        edgeCount: edges.length,
      })
    }

    if (paths.length === 0) {
      const startNode = await GraphManager.getNode(startNodeId)
      if (startNode) {
        paths.push({
          nodes: [startNode],
          edges: [],
          totalWeight: 0,
          nodeCount: 1,
          edgeCount: 0,
        })
      }
    }

    return paths
  },

  async dfs(startNodeId: string, maxDepth: number = 5): Promise<GraphPath[]> {
    const client = Neo4jClient.getDriver()
    if (!client) return []

    const result = await Neo4jClient.run(
      `MATCH (start:GraphNode {nodeId: $startNodeId})
       CALL apoc.path.spanningTree(start, {}, {}, $maxDepth, '') YIELD path
       WITH path, nodes(path) AS ns, relationships(path) AS rs
       RETURN ns, rs`,
      { startNodeId, maxDepth },
    )

    const paths: GraphPath[] = []
    for (const record of result.records) {
      const ns = record.get("ns") as Array<Record<string, unknown>>
      const rs = record.get("rs") as Array<Record<string, unknown>>

      const nodes = ns.map((n) => deserializePathNode(n.properties as Record<string, unknown>))
      const edges = rs.map((r) => deserializePathEdge(r.properties as Record<string, unknown>))

      paths.push({
        nodes,
        edges,
        totalWeight: edges.reduce((sum, e) => sum + e.weight, 0),
        nodeCount: nodes.length,
        edgeCount: edges.length,
      })
    }

    if (paths.length === 0) {
      const startNode = await GraphManager.getNode(startNodeId)
      if (startNode) {
        paths.push({
          nodes: [startNode],
          edges: [],
          totalWeight: 0,
          nodeCount: 1,
          edgeCount: 0,
        })
      }
    }

    return paths
  },

  async shortestPath(startNodeId: string, endNodeId: string): Promise<GraphPath | null> {
    if (startNodeId === endNodeId) {
      const node = await GraphManager.getNode(startNodeId)
      if (!node) return null
      return { nodes: [node], edges: [], totalWeight: 0, nodeCount: 1, edgeCount: 0 }
    }

    const client = Neo4jClient.getDriver()
    if (!client) return null

    const result = await Neo4jClient.run(
      `MATCH (start:GraphNode {nodeId: $startNodeId})
       MATCH (end:GraphNode {nodeId: $endNodeId})
       MATCH path = shortestPath((start)-[:GRAPH_EDGE*]-(end))
       RETURN nodes(path) AS ns, relationships(path) AS rs`,
      { startNodeId, endNodeId },
    )

    if (result.records.length === 0) return null

    const record = result.records[0]
    const ns = record.get("ns") as Array<Record<string, unknown>>
    const rs = record.get("rs") as Array<Record<string, unknown>>

      const nodes = ns.map((n) => deserializePathNode(n.properties as Record<string, unknown>))
      const edges = rs.map((r) => deserializePathEdge(r.properties as Record<string, unknown>))

    return {
      nodes,
      edges,
      totalWeight: edges.reduce((sum, e) => sum + e.weight, 0),
      nodeCount: nodes.length,
      edgeCount: edges.length,
    }
  },

  async connectedComponents(): Promise<GraphNode[][]> {
    const client = Neo4jClient.getDriver()
    if (!client) return []

    const result = await Neo4jClient.run(
      `MATCH (n:GraphNode)
       CALL {
         WITH n
         MATCH path = (n)-[:GRAPH_EDGE*0..]-(m:GraphNode)
         WITH collect(DISTINCT m) AS component
         RETURN component
       }
       RETURN component`,
    )

    const components: GraphNode[][] = []
    for (const record of result.records) {
      const component = record.get("component") as Array<Record<string, unknown>>
      components.push(component.map((n) => deserializePathNode(n.properties as Record<string, unknown>)))
    }

    return components
  },

  async neighborhood(nodeId: string, depth: number = 1): Promise<GraphNeighborhood> {
    const centerNode = await GraphManager.getNode(nodeId)
    if (!centerNode) throw new Error(`Node ${nodeId} not found`)

    const client = Neo4jClient.getDriver()
    if (!client) {
      return {
        centerNode,
        nodes: [],
        edges: [],
        depth,
        nodeCount: 0,
        edgeCount: 0,
      }
    }

    const result = await Neo4jClient.run(
      `MATCH (center:GraphNode {nodeId: $nodeId})
       MATCH (center)-[e:GRAPH_EDGE*1..${depth}]-(neighbor:GraphNode)
       WITH DISTINCT neighbor, e
       RETURN neighbor, e`,
      { nodeId },
    )

    const nodeMap = new Map<string, GraphNode>()
    const edgeMap = new Map<string, GraphEdge>()

    for (const record of result.records) {
      const neighbor = deserializePathNode(record.get("neighbor").properties)
      nodeMap.set(neighbor.id, neighbor)

      const edges = record.get("e") as Array<Record<string, unknown>>
      for (const edgeRecord of edges) {
        const edge = deserializePathEdge(edgeRecord.properties as Record<string, unknown>)
        edgeMap.set(edge.id, edge)
      }
    }

    return {
      centerNode,
      nodes: Array.from(nodeMap.values()),
      edges: Array.from(edgeMap.values()),
      depth,
      nodeCount: nodeMap.size,
      edgeCount: edgeMap.size,
    }
  },

  async reachableNodes(startNodeId: string): Promise<GraphNode[]> {
    const client = Neo4jClient.getDriver()
    if (!client) return []

    const result = await Neo4jClient.run(
      `MATCH (start:GraphNode {nodeId: $startNodeId})
       MATCH (start)-[:GRAPH_EDGE*1..]-(neighbor:GraphNode)
       RETURN DISTINCT neighbor`,
      { startNodeId },
    )

    return result.records.map((record) => deserializePathNode(record.get("neighbor").properties))
  },
}
