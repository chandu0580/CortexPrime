import type { GraphMetrics } from "./types"
import { Neo4jClient } from "./Neo4jClient"

export const GraphMetricsCollector = {
  async initialize(systemId: string): Promise<void> {
    const client = Neo4jClient.getDriver()
    if (!client) return

    const result = await Neo4jClient.run(
      `MATCH (m:MetricsSystem {systemId: $systemId}) RETURN m`,
      { systemId },
    )

    if (result.records.length === 0) {
      await Neo4jClient.run(
        `CREATE (m:MetricsSystem {
          systemId: $systemId,
          totalEntities: 0,
          activeEntities: 0,
          totalRelationships: 0,
          graphNodes: 0,
          graphEdges: 0,
          totalTraversals: 0,
          totalInferences: 0,
          totalValidations: 0,
          totalClusters: 0,
          duplicateEntities: 0,
          orphanNodes: 0,
          confidenceSum: 0,
          confidenceCount: 0,
          startedAt: $startedAt
        }) RETURN m`,
        { systemId, startedAt: new Date().toISOString() },
      )
    }
  },

  async recordEntity(systemId: string, status: string): Promise<void> {
    const client = Neo4jClient.getDriver()
    if (!client) return

    await Neo4jClient.run(
      `MATCH (m:MetricsSystem {systemId: $systemId})
       SET m.totalEntities = m.totalEntities + 1
       ${status === "active" ? "SET m.activeEntities = m.activeEntities + 1" : ""}`,
      { systemId },
    )
  },

  async recordRelationship(systemId: string, count: number = 1): Promise<void> {
    const client = Neo4jClient.getDriver()
    if (!client) return

    await Neo4jClient.run(
      `MATCH (m:MetricsSystem {systemId: $systemId})
       SET m.totalRelationships = m.totalRelationships + $count`,
      { systemId, count },
    )
  },

  async recordGraphNode(systemId: string, count: number = 1): Promise<void> {
    const client = Neo4jClient.getDriver()
    if (!client) return

    await Neo4jClient.run(
      `MATCH (m:MetricsSystem {systemId: $systemId})
       SET m.graphNodes = m.graphNodes + $count`,
      { systemId, count },
    )
  },

  async recordGraphEdge(systemId: string, count: number = 1): Promise<void> {
    const client = Neo4jClient.getDriver()
    if (!client) return

    await Neo4jClient.run(
      `MATCH (m:MetricsSystem {systemId: $systemId})
       SET m.graphEdges = m.graphEdges + $count`,
      { systemId, count },
    )
  },

  async recordTraversal(systemId: string): Promise<void> {
    const client = Neo4jClient.getDriver()
    if (!client) return

    await Neo4jClient.run(
      `MATCH (m:MetricsSystem {systemId: $systemId})
       SET m.totalTraversals = m.totalTraversals + 1`,
      { systemId },
    )
  },

  async recordInference(systemId: string, count: number = 1): Promise<void> {
    const client = Neo4jClient.getDriver()
    if (!client) return

    await Neo4jClient.run(
      `MATCH (m:MetricsSystem {systemId: $systemId})
       SET m.totalInferences = m.totalInferences + $count`,
      { systemId, count },
    )
  },

  async recordValidation(systemId: string): Promise<void> {
    const client = Neo4jClient.getDriver()
    if (!client) return

    await Neo4jClient.run(
      `MATCH (m:MetricsSystem {systemId: $systemId})
       SET m.totalValidations = m.totalValidations + 1`,
      { systemId },
    )
  },

  async recordCluster(systemId: string, count: number = 1): Promise<void> {
    const client = Neo4jClient.getDriver()
    if (!client) return

    await Neo4jClient.run(
      `MATCH (m:MetricsSystem {systemId: $systemId})
       SET m.totalClusters = m.totalClusters + $count`,
      { systemId, count },
    )
  },

  async recordConfidence(systemId: string, score: number): Promise<void> {
    const client = Neo4jClient.getDriver()
    if (!client) return

    await Neo4jClient.run(
      `MATCH (m:MetricsSystem {systemId: $systemId})
       SET m.confidenceSum = m.confidenceSum + $score,
           m.confidenceCount = m.confidenceCount + 1`,
      { systemId, score },
    )
  },

  async setDuplicateEntities(systemId: string, count: number): Promise<void> {
    const client = Neo4jClient.getDriver()
    if (!client) return

    await Neo4jClient.run(
      `MATCH (m:MetricsSystem {systemId: $systemId})
       SET m.duplicateEntities = $count`,
      { systemId, count },
    )
  },

  async setOrphanNodes(systemId: string, count: number): Promise<void> {
    const client = Neo4jClient.getDriver()
    if (!client) return

    await Neo4jClient.run(
      `MATCH (m:MetricsSystem {systemId: $systemId})
       SET m.orphanNodes = $count`,
      { systemId, count },
    )
  },

  async collect(systemId: string, graphDensity: number, connectedComponents: number): Promise<GraphMetrics> {
    const client = Neo4jClient.getDriver()
    if (!client) {
      return {
        systemId, totalEntities: 0, activeEntities: 0, totalRelationships: 0,
        graphNodes: 0, graphEdges: 0, graphDensity: 0, connectedComponents: 0,
        totalTraversals: 0, totalInferences: 0, totalValidations: 0,
        totalClusters: 0, avgConfidence: 0, duplicateEntities: 0, orphanNodes: 0,
        collectedAt: new Date().toISOString(),
      }
    }

    const result = await Neo4jClient.run(
      `MATCH (m:MetricsSystem {systemId: $systemId}) RETURN m`,
      { systemId },
    )

    if (result.records.length === 0) {
      return {
        systemId, totalEntities: 0, activeEntities: 0, totalRelationships: 0,
        graphNodes: 0, graphEdges: 0, graphDensity: 0, connectedComponents: 0,
        totalTraversals: 0, totalInferences: 0, totalValidations: 0,
        totalClusters: 0, avgConfidence: 0, duplicateEntities: 0, orphanNodes: 0,
        collectedAt: new Date().toISOString(),
      }
    }

    const props = result.records[0].get("m").properties
    const confidenceCount = props.confidenceCount as number
    const confidenceSum = props.confidenceSum as number
    const avgConf = confidenceCount > 0
      ? Math.round((confidenceSum / confidenceCount) * 100) / 100
      : 0

    return {
      systemId,
      totalEntities: (props.totalEntities as number) ?? 0,
      activeEntities: (props.activeEntities as number) ?? 0,
      totalRelationships: (props.totalRelationships as number) ?? 0,
      graphNodes: (props.graphNodes as number) ?? 0,
      graphEdges: (props.graphEdges as number) ?? 0,
      graphDensity,
      connectedComponents,
      totalTraversals: (props.totalTraversals as number) ?? 0,
      totalInferences: (props.totalInferences as number) ?? 0,
      totalValidations: (props.totalValidations as number) ?? 0,
      totalClusters: (props.totalClusters as number) ?? 0,
      avgConfidence: avgConf,
      duplicateEntities: (props.duplicateEntities as number) ?? 0,
      orphanNodes: (props.orphanNodes as number) ?? 0,
      collectedAt: new Date().toISOString(),
    }
  },

  async reset(systemId: string): Promise<void> {
    const client = Neo4jClient.getDriver()
    if (!client) return

    await Neo4jClient.run(
      `MATCH (m:MetricsSystem {systemId: $systemId}) DELETE m`,
      { systemId },
    )
  },
}
