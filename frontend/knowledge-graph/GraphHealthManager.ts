import type { GraphHealth, GraphHealthStatus } from "./types"
import { Neo4jClient } from "./Neo4jClient"

export const GraphHealthManager = {
  async initialize(systemId: string): Promise<void> {
    const client = Neo4jClient.getDriver()
    if (!client) return

    const result = await Neo4jClient.run(
      `MATCH (h:HealthSystem {systemId: $systemId}) RETURN h`,
      { systemId },
    )

    if (result.records.length === 0) {
      await Neo4jClient.run(
        `CREATE (h:HealthSystem {
          systemId: $systemId,
          totalEntities: 0,
          totalRelationships: 0,
          orphanNodes: 0,
          invalidEdges: 0,
          duplicateEntities: 0,
          disconnectedComponents: 0,
          consistencyScore: 100,
          consecutiveFailures: 0,
          lastCheckAt: ''
        }) RETURN h`,
        { systemId },
      )
    }
  },

  async recordIntegrity(systemId: string, data: {
    totalEntities: number
    totalRelationships: number
    orphanNodes: number
    invalidEdges: number
    duplicateEntities: number
    disconnectedComponents: number
    consistencyScore: number
  }): Promise<void> {
    const client = Neo4jClient.getDriver()
    if (!client) return

    await Neo4jClient.run(
      `MATCH (h:HealthSystem {systemId: $systemId})
       SET h.totalEntities = $totalEntities,
           h.totalRelationships = $totalRelationships,
           h.orphanNodes = $orphanNodes,
           h.invalidEdges = $invalidEdges,
           h.duplicateEntities = $duplicateEntities,
           h.disconnectedComponents = $disconnectedComponents,
           h.consistencyScore = $consistencyScore,
           h.lastCheckAt = $lastCheckAt`,
      {
        systemId,
        ...data,
        lastCheckAt: new Date().toISOString(),
      },
    )
  },

  async recordFailure(systemId: string): Promise<void> {
    const client = Neo4jClient.getDriver()
    if (!client) return

    await Neo4jClient.run(
      `MATCH (h:HealthSystem {systemId: $systemId})
       SET h.consecutiveFailures = h.consecutiveFailures + 1`,
      { systemId },
    )
  },

  async recordSuccess(systemId: string): Promise<void> {
    const client = Neo4jClient.getDriver()
    if (!client) return

    await Neo4jClient.run(
      `MATCH (h:HealthSystem {systemId: $systemId})
       SET h.consecutiveFailures = 0`,
      { systemId },
    )
  },

  async check(systemId: string): Promise<GraphHealth> {
    const client = Neo4jClient.getDriver()
    if (!client) {
      return {
        systemId, status: "unknown", totalEntities: 0, totalRelationships: 0,
        orphanNodes: 0, invalidEdges: 0, duplicateEntities: 0,
        disconnectedComponents: 0, consistencyScore: 100,
        recoveryReady: false, message: "Neo4j not connected",
        timestamp: new Date().toISOString(),
      }
    }

    const result = await Neo4jClient.run(
      `MATCH (h:HealthSystem {systemId: $systemId}) RETURN h`,
      { systemId },
    )

    if (result.records.length === 0) {
      return {
        systemId, status: "unknown", totalEntities: 0, totalRelationships: 0,
        orphanNodes: 0, invalidEdges: 0, duplicateEntities: 0,
        disconnectedComponents: 0, consistencyScore: 100,
        recoveryReady: false, message: "Health state not initialized",
        timestamp: new Date().toISOString(),
      }
    }

    const props = result.records[0].get("h").properties
    const consecutiveFailures = (props.consecutiveFailures as number) ?? 0
    const orphanNodes = (props.orphanNodes as number) ?? 0
    const invalidEdges = (props.invalidEdges as number) ?? 0
    const duplicateEntities = (props.duplicateEntities as number) ?? 0
    const consistencyScore = (props.consistencyScore as number) ?? 100

    let status: GraphHealthStatus = "healthy"
    let message = "Knowledge graph is operating normally"
    let recoveryReady = false

    if (consecutiveFailures >= 5) {
      status = "unhealthy"
      message = `${consecutiveFailures} consecutive failures detected`
      recoveryReady = true
    } else if (consecutiveFailures >= 3) {
      status = "degraded"
      message = `${consecutiveFailures} consecutive failures detected`
      recoveryReady = true
    }

    if (status !== "unhealthy") {
      if (consistencyScore < 70) {
        status = "degraded"
        message = `Consistency score ${consistencyScore}% is below threshold`
        recoveryReady = true
      } else if (orphanNodes > 20) {
        status = "degraded"
        message = `${orphanNodes} orphan nodes detected`
        recoveryReady = true
      } else if (duplicateEntities > 5) {
        status = "degraded"
        message = `${duplicateEntities} duplicate entity groups detected`
        recoveryReady = true
      } else if (invalidEdges > 10) {
        status = "degraded"
        message = `${invalidEdges} invalid edges detected`
        recoveryReady = true
      }
    }

    return {
      systemId, status,
      totalEntities: (props.totalEntities as number) ?? 0,
      totalRelationships: (props.totalRelationships as number) ?? 0,
      orphanNodes,
      invalidEdges,
      duplicateEntities,
      disconnectedComponents: (props.disconnectedComponents as number) ?? 0,
      consistencyScore,
      recoveryReady, message,
      timestamp: new Date().toISOString(),
    }
  },

  async getConsecutiveFailures(systemId: string): Promise<number> {
    const client = Neo4jClient.getDriver()
    if (!client) return 0

    const result = await Neo4jClient.run(
      `MATCH (h:HealthSystem {systemId: $systemId}) RETURN h.consecutiveFailures AS failures`,
      { systemId },
    )

    if (result.records.length === 0) return 0
    return result.records[0].get("failures") ?? 0
  },

  async reset(systemId: string): Promise<void> {
    const client = Neo4jClient.getDriver()
    if (!client) return

    await Neo4jClient.run(
      `MATCH (h:HealthSystem {systemId: $systemId}) DELETE h`,
      { systemId },
    )
  },
}
