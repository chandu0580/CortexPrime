import type { MemoryHealth, MemoryHealthStatus } from "./types"
import { RedisClient } from "./RedisClient"

const HEALTH_KEY = "health"

export const MemoryHealthManager = {
  async initialize(systemId: string): Promise<void> {
    const client = RedisClient.getClient()
    if (!client) return
    const exists = await client.exists(`${HEALTH_KEY}:${systemId}`)
    if (!exists) {
      await client.hset(`${HEALTH_KEY}:${systemId}`, {
        totalEntries: "0",
        activeEntries: "0",
        expiredEntries: "0",
        orphanNodes: "0",
        brokenEdges: "0",
        graphConsistent: "1",
        expirationBacklog: "0",
        consecutiveFailures: "0",
        lastCheckAt: "",
      })
    }
  },

  async recordIntegrity(systemId: string, data: {
    totalEntries: number
    activeEntries: number
    expiredEntries: number
    orphanNodes: number
    brokenEdges: number
    expirationBacklog: number
  }): Promise<void> {
    const client = RedisClient.getClient()
    if (!client) return
    await client.hset(`${HEALTH_KEY}:${systemId}`, {
      totalEntries: String(data.totalEntries),
      activeEntries: String(data.activeEntries),
      expiredEntries: String(data.expiredEntries),
      orphanNodes: String(data.orphanNodes),
      brokenEdges: String(data.brokenEdges),
      graphConsistent: data.brokenEdges === 0 ? "1" : "0",
      expirationBacklog: String(data.expirationBacklog),
      lastCheckAt: new Date().toISOString(),
    })
  },

  async recordFailure(systemId: string): Promise<void> {
    const client = RedisClient.getClient()
    if (!client) return
    await client.hincrby(`${HEALTH_KEY}:${systemId}`, "consecutiveFailures", 1)
  },

  async recordSuccess(systemId: string): Promise<void> {
    const client = RedisClient.getClient()
    if (!client) return
    await client.hset(`${HEALTH_KEY}:${systemId}`, { consecutiveFailures: "0" })
  },

  async check(systemId: string): Promise<MemoryHealth> {
    const client = RedisClient.getClient()
    if (!client) {
      return {
        systemId,
        status: "unknown",
        totalEntries: 0, activeEntries: 0, expiredEntries: 0,
        orphanNodes: 0, brokenEdges: 0, graphConsistent: true,
        expirationBacklog: 0, recoveryReady: false,
        message: "Redis not connected",
        timestamp: new Date().toISOString(),
      }
    }

    const data = await client.hgetall(`${HEALTH_KEY}:${systemId}`)
    if (!data || Object.keys(data).length === 0) {
      return {
        systemId,
        status: "unknown",
        totalEntries: 0, activeEntries: 0, expiredEntries: 0,
        orphanNodes: 0, brokenEdges: 0, graphConsistent: true,
        expirationBacklog: 0, recoveryReady: false,
        message: "Health state not initialized",
        timestamp: new Date().toISOString(),
      }
    }

    const consecutiveFailures = parseInt(data.consecutiveFailures || "0", 10)
    const orphanNodes = parseInt(data.orphanNodes || "0", 10)
    const brokenEdges = parseInt(data.brokenEdges || "0", 10)
    const graphConsistent = data.graphConsistent === "1"
    const expirationBacklog = parseInt(data.expirationBacklog || "0", 10)

    let status: MemoryHealthStatus = "healthy"
    let message = "Memory system is operating normally"
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
      if (orphanNodes > 100) {
        status = "degraded"
        message = `${orphanNodes} orphan nodes detected`
        recoveryReady = true
      } else if (!graphConsistent) {
        status = "degraded"
        message = `${brokenEdges} broken graph edges detected`
        recoveryReady = true
      } else if (expirationBacklog > 50) {
        status = "degraded"
        message = `${expirationBacklog} entries pending expiration`
        recoveryReady = true
      }
    }

    return {
      systemId,
      status,
      totalEntries: parseInt(data.totalEntries || "0", 10),
      activeEntries: parseInt(data.activeEntries || "0", 10),
      expiredEntries: parseInt(data.expiredEntries || "0", 10),
      orphanNodes,
      brokenEdges,
      graphConsistent,
      expirationBacklog,
      recoveryReady,
      message,
      timestamp: new Date().toISOString(),
    }
  },

  async getConsecutiveFailures(systemId: string): Promise<number> {
    const client = RedisClient.getClient()
    if (!client) return 0
    const data = await client.hget(`${HEALTH_KEY}:${systemId}`, "consecutiveFailures")
    return parseInt(data || "0", 10)
  },

  async reset(systemId: string): Promise<void> {
    const client = RedisClient.getClient()
    if (!client) return
    await client.del(`${HEALTH_KEY}:${systemId}`)
  },
}
