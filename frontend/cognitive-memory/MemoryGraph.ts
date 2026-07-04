import type { MemoryGraphNode, MemoryGraphEdge, MemoryRelationshipType, MemoryType } from "./types"
import { generateId } from "@/worker-framework/shared"
import { RedisClient } from "./RedisClient"

const NODE_KEY = "graph:node"
const EDGE_KEY = "graph:edge"
const ENTRY_INDEX_KEY = "graph:entry"
const EDGE_SOURCE_INDEX_KEY = "graph:edge:source"
const EDGE_TARGET_INDEX_KEY = "graph:edge:target"

function serializeNode(node: MemoryGraphNode): Record<string, string> {
  return {
    id: node.id,
    entryId: node.entryId,
    type: node.type,
    label: node.label,
    properties: JSON.stringify(node.properties),
  }
}

function deserializeNode(data: Record<string, string>): MemoryGraphNode {
  return {
    id: data.id,
    entryId: data.entryId,
    type: data.type as MemoryType,
    label: data.label,
    properties: JSON.parse(data.properties || "{}"),
  }
}

function serializeEdge(edge: MemoryGraphEdge): Record<string, string> {
  return {
    id: edge.id,
    sourceNodeId: edge.sourceNodeId,
    targetNodeId: edge.targetNodeId,
    relationship: edge.relationship,
    weight: String(edge.weight),
    createdAt: edge.createdAt,
  }
}

function deserializeEdge(data: Record<string, string>): MemoryGraphEdge {
  return {
    id: data.id,
    sourceNodeId: data.sourceNodeId,
    targetNodeId: data.targetNodeId,
    relationship: data.relationship as MemoryRelationshipType,
    weight: parseFloat(data.weight) || 1.0,
    createdAt: data.createdAt,
  }
}

async function getEdgeById(edgeId: string): Promise<MemoryGraphEdge | null> {
  const client = RedisClient.getClient()
  if (!client) return null
  const data = await client.hgetall(`${EDGE_KEY}:${edgeId}`)
  if (!data || Object.keys(data).length === 0) return null
  return deserializeEdge(data)
}

export const MemoryGraph = {
  async addNode(entryId: string, type: MemoryType, label: string, properties?: Record<string, string>): Promise<MemoryGraphNode> {
    const node: MemoryGraphNode = {
      id: generateId("mem-graph-node"),
      entryId,
      type,
      label,
      properties: properties ?? {},
    }
    const client = RedisClient.getClient()
    if (client) {
      await client.hset(`${NODE_KEY}:${node.id}`, serializeNode(node))
      await client.hset(`${ENTRY_INDEX_KEY}:${entryId}`, { nodeId: node.id })
    }
    return node
  },

  async getNode(nodeId: string): Promise<MemoryGraphNode | null> {
    const client = RedisClient.getClient()
    if (!client) return null
    const data = await client.hgetall(`${NODE_KEY}:${nodeId}`)
    if (!data || Object.keys(data).length === 0) return null
    return deserializeNode(data)
  },

  async findNodeByEntryId(entryId: string): Promise<MemoryGraphNode | null> {
    const client = RedisClient.getClient()
    if (!client) return null
    const data = await client.hgetall(`${ENTRY_INDEX_KEY}:${entryId}`)
    if (!data || !data.nodeId) return null
    return this.getNode(data.nodeId)
  },

  async addEdge(
    sourceNodeId: string,
    targetNodeId: string,
    relationship: MemoryRelationshipType,
    weight: number = 1.0,
  ): Promise<MemoryGraphEdge> {
    const source = await this.getNode(sourceNodeId)
    const target = await this.getNode(targetNodeId)
    if (!source) throw new Error(`Source node ${sourceNodeId} not found`)
    if (!target) throw new Error(`Target node ${targetNodeId} not found`)

    const edge: MemoryGraphEdge = {
      id: generateId("mem-graph-edge"),
      sourceNodeId,
      targetNodeId,
      relationship,
      weight,
      createdAt: new Date().toISOString(),
    }

    const client = RedisClient.getClient()
    if (client) {
      await client.hset(`${EDGE_KEY}:${edge.id}`, serializeEdge(edge))
      await client.sadd(`${EDGE_SOURCE_INDEX_KEY}:${sourceNodeId}`, edge.id)
      await client.sadd(`${EDGE_TARGET_INDEX_KEY}:${targetNodeId}`, edge.id)
    }
    return edge
  },

  async getEdges(): Promise<MemoryGraphEdge[]> {
    const client = RedisClient.getClient()
    if (!client) return []
    const keys = await client.keys(`${EDGE_KEY}:*`)
    const edges: MemoryGraphEdge[] = []
    for (const key of keys) {
      const data = await client.hgetall(key)
      if (data && Object.keys(data).length > 0) {
        edges.push(deserializeEdge(data))
      }
    }
    return edges
  },

  async getNeighbors(nodeId: string): Promise<{ node: MemoryGraphNode; edge: MemoryGraphEdge }[]> {
    const client = RedisClient.getClient()
    if (!client) return []
    const neighbors: { node: MemoryGraphNode; edge: MemoryGraphEdge }[] = []

    const sourceEdgeIds = await client.smembers(`${EDGE_SOURCE_INDEX_KEY}:${nodeId}`)
    for (const edgeId of sourceEdgeIds) {
      const edge = await getEdgeById(edgeId)
      if (edge) {
        const node = await this.getNode(edge.targetNodeId)
        if (node) neighbors.push({ node, edge })
      }
    }

    const targetEdgeIds = await client.smembers(`${EDGE_TARGET_INDEX_KEY}:${nodeId}`)
    for (const edgeId of targetEdgeIds) {
      const edge = await getEdgeById(edgeId)
      if (edge) {
        const node = await this.getNode(edge.sourceNodeId)
        if (node) neighbors.push({ node, edge })
      }
    }

    return neighbors
  },

  async traverse(nodeId: string, depth: number): Promise<{ nodes: MemoryGraphNode[]; edges: MemoryGraphEdge[] }> {
    const visitedNodes = new Set<string>()
    const visitedEdges = new Set<string>()
    const resultNodes: MemoryGraphNode[] = []
    const resultEdges: MemoryGraphEdge[] = []

    const queue: Array<{ nodeId: string; currentDepth: number }> = [{ nodeId, currentDepth: 0 }]
    visitedNodes.add(nodeId)

    while (queue.length > 0) {
      const { nodeId: currentId, currentDepth } = queue.shift()!
      const node = await this.getNode(currentId)
      if (node) resultNodes.push(node)

      if (currentDepth >= depth) continue

      const neighbors = await this.getNeighbors(currentId)
      for (const { node: neighbor, edge } of neighbors) {
        if (!visitedNodes.has(neighbor.id)) {
          visitedNodes.add(neighbor.id)
          visitedEdges.add(edge.id)
          resultEdges.push(edge)
          queue.push({ nodeId: neighbor.id, currentDepth: currentDepth + 1 })
        }
      }
    }

    return { nodes: resultNodes, edges: resultEdges }
  },

  async findConnectedComponents(): Promise<string[][]> {
    const client = RedisClient.getClient()
    if (!client) return []
    const nodeKeys = await client.keys(`${NODE_KEY}:*`)
    const visited = new Set<string>()
    const components: string[][] = []

    for (const key of nodeKeys) {
      const nodeId = key.replace(`${NODE_KEY}:`, "")
      if (visited.has(nodeId)) continue

      const component: string[] = []
      const queue: string[] = [nodeId]
      visited.add(nodeId)

      while (queue.length > 0) {
        const currentId = queue.shift()!
        component.push(currentId)

        const neighbors = await this.getNeighbors(currentId)
        for (const { node } of neighbors) {
          if (!visited.has(node.id)) {
            visited.add(node.id)
            queue.push(node.id)
          }
        }
      }

      if (component.length > 0) components.push(component)
    }

    return components
  },

  async getGraphDensity(): Promise<number> {
    const client = RedisClient.getClient()
    if (!client) return 0
    const nodeKeys = await client.keys(`${NODE_KEY}:*`)
    const edgeKeys = await client.keys(`${EDGE_KEY}:*`)
    const nodeCount = nodeKeys.length
    if (nodeCount <= 1) return 0
    const edgeCount = edgeKeys.length
    const maxEdges = (nodeCount * (nodeCount - 1)) / 2
    return edgeCount / maxEdges
  },

  async removeOrphanNodes(): Promise<string[]> {
    const client = RedisClient.getClient()
    if (!client) return []
    const nodeKeys = await client.keys(`${NODE_KEY}:*`)
    const connectedNodeIds = new Set<string>()

    const edgeKeys = await client.keys(`${EDGE_KEY}:*`)
    for (const key of edgeKeys) {
      const data = await client.hgetall(key)
      if (data) {
        connectedNodeIds.add(data.sourceNodeId)
        connectedNodeIds.add(data.targetNodeId)
      }
    }

    const orphanIds: string[] = []
    for (const key of nodeKeys) {
      const nodeId = key.replace(`${NODE_KEY}:`, "")
      if (!connectedNodeIds.has(nodeId)) {
        orphanIds.push(nodeId)
        await client.del(key)
      }
    }
    return orphanIds
  },

  async removeBrokenEdges(): Promise<string[]> {
    const client = RedisClient.getClient()
    if (!client) return []
    const edgeKeys = await client.keys(`${EDGE_KEY}:*`)
    const brokenIds: string[] = []

    for (const key of edgeKeys) {
      const data = await client.hgetall(key)
      if (!data) continue
      const sourceExists = await client.exists(`${NODE_KEY}:${data.sourceNodeId}`)
      const targetExists = await client.exists(`${NODE_KEY}:${data.targetNodeId}`)
      if (!sourceExists || !targetExists) {
        brokenIds.push(data.id)
        await client.del(key)
        await client.srem(`${EDGE_SOURCE_INDEX_KEY}:${data.sourceNodeId}`, data.id)
        await client.srem(`${EDGE_TARGET_INDEX_KEY}:${data.targetNodeId}`, data.id)
      }
    }
    return brokenIds
  },

  async countNodes(): Promise<number> {
    const client = RedisClient.getClient()
    if (!client) return 0
    const keys = await client.keys(`${NODE_KEY}:*`)
    return keys.length
  },

  async countEdges(): Promise<number> {
    const client = RedisClient.getClient()
    if (!client) return 0
    const keys = await client.keys(`${EDGE_KEY}:*`)
    return keys.length
  },

  async clearAll(): Promise<void> {
    const client = RedisClient.getClient()
    if (!client) return
    await RedisClient.flushPrefix("graph:")
  },
}
