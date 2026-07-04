import type { MemoryMetrics } from "./types"
import { RedisClient } from "./RedisClient"

const METRICS_KEY = "metrics"

export const MemoryMetricsCollector = {
  async initialize(systemId: string): Promise<void> {
    const client = RedisClient.getClient()
    if (!client) return
    const exists = await client.exists(`${METRICS_KEY}:${systemId}:startedAt`)
    if (!exists) {
      await client.hset(`${METRICS_KEY}:${systemId}`, {
        totalEntries: "0",
        workingCount: "0",
        episodicCount: "0",
        semanticCount: "0",
        proceduralCount: "0",
        totalAssociations: "0",
        graphNodes: "0",
        graphEdges: "0",
        activeSessions: "0",
        totalSnapshots: "0",
        totalRecalls: "0",
        expiredEntries: "0",
        orphanNodes: "0",
        startedAt: new Date().toISOString(),
      })
    }
  },

  async recordEntry(systemId: string, type: string, count: number = 1): Promise<void> {
    const client = RedisClient.getClient()
    if (!client) return
    await client.hincrby(`${METRICS_KEY}:${systemId}`, "totalEntries", count)
    await client.hincrby(`${METRICS_KEY}:${systemId}`, `${type}Count`, count)
  },

  async recordAssociation(systemId: string, count: number = 1): Promise<void> {
    const client = RedisClient.getClient()
    if (!client) return
    await client.hincrby(`${METRICS_KEY}:${systemId}`, "totalAssociations", count)
  },

  async recordGraphNode(systemId: string, count: number = 1): Promise<void> {
    const client = RedisClient.getClient()
    if (!client) return
    await client.hincrby(`${METRICS_KEY}:${systemId}`, "graphNodes", count)
  },

  async recordGraphEdge(systemId: string, count: number = 1): Promise<void> {
    const client = RedisClient.getClient()
    if (!client) return
    await client.hincrby(`${METRICS_KEY}:${systemId}`, "graphEdges", count)
  },

  async recordSnapshot(systemId: string): Promise<void> {
    const client = RedisClient.getClient()
    if (!client) return
    await client.hincrby(`${METRICS_KEY}:${systemId}`, "totalSnapshots", 1)
  },

  async recordRecall(systemId: string, durationMs: number): Promise<void> {
    const client = RedisClient.getClient()
    if (!client) return
    await client.hincrby(`${METRICS_KEY}:${systemId}`, "totalRecalls", 1)
    await client.rpush(`${METRICS_KEY}:${systemId}:recallDurations`, String(durationMs))
    await client.ltrim(`${METRICS_KEY}:${systemId}:recallDurations`, -1000, -1)
  },

  async recordExpired(systemId: string, count: number = 1): Promise<void> {
    const client = RedisClient.getClient()
    if (!client) return
    await client.hincrby(`${METRICS_KEY}:${systemId}`, "expiredEntries", count)
  },

  async recordOrphan(systemId: string, count: number = 1): Promise<void> {
    const client = RedisClient.getClient()
    if (!client) return
    await client.hincrby(`${METRICS_KEY}:${systemId}`, "orphanNodes", count)
  },

  async setActiveSessions(systemId: string, count: number): Promise<void> {
    const client = RedisClient.getClient()
    if (!client) return
    await client.hset(`${METRICS_KEY}:${systemId}`, { activeSessions: String(count) })
  },

  async collect(systemId: string, graphDensity: number): Promise<MemoryMetrics> {
    const client = RedisClient.getClient()
    if (!client) {
      return {
        systemId,
        totalEntries: 0, workingCount: 0, episodicCount: 0, semanticCount: 0, proceduralCount: 0,
        totalAssociations: 0, graphNodes: 0, graphEdges: 0, graphDensity: 0,
        activeSessions: 0, totalSnapshots: 0, totalRecalls: 0, averageRecallDurationMs: 0,
        expiredEntries: 0, orphanNodes: 0, memoryGrowthBytes: 0,
        collectedAt: new Date().toISOString(),
      }
    }

    const data = await client.hgetall(`${METRICS_KEY}:${systemId}`)
    const durations = await client.lrange(`${METRICS_KEY}:${systemId}:recallDurations`, 0, -1)

    const totalEntries = parseInt(data.totalEntries || "0", 10)
    const totalRecalls = parseInt(data.totalRecalls || "0", 10)
    const avgRecall = durations.length > 0
      ? Math.round(durations.reduce((a, b) => a + parseInt(b, 10), 0) / durations.length)
      : 0

    const startedAt = data.startedAt ?? new Date().toISOString()
    const uptime = Date.now() - new Date(startedAt).getTime()
    const growthRate = uptime > 0 ? Math.round((totalEntries / uptime) * 60000 * 1024) : 0

    return {
      systemId,
      totalEntries,
      workingCount: parseInt(data.workingCount || "0", 10),
      episodicCount: parseInt(data.episodicCount || "0", 10),
      semanticCount: parseInt(data.semanticCount || "0", 10),
      proceduralCount: parseInt(data.proceduralCount || "0", 10),
      totalAssociations: parseInt(data.totalAssociations || "0", 10),
      graphNodes: parseInt(data.graphNodes || "0", 10),
      graphEdges: parseInt(data.graphEdges || "0", 10),
      graphDensity,
      activeSessions: parseInt(data.activeSessions || "0", 10),
      totalSnapshots: parseInt(data.totalSnapshots || "0", 10),
      totalRecalls,
      averageRecallDurationMs: avgRecall,
      expiredEntries: parseInt(data.expiredEntries || "0", 10),
      orphanNodes: parseInt(data.orphanNodes || "0", 10),
      memoryGrowthBytes: growthRate,
      collectedAt: new Date().toISOString(),
    }
  },

  async reset(systemId: string): Promise<void> {
    const client = RedisClient.getClient()
    if (!client) return
    await client.del(`${METRICS_KEY}:${systemId}`, `${METRICS_KEY}:${systemId}:recallDurations`)
  },
}
