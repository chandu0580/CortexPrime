import type { ResourceHealth, ResourceStatus, ResourcePool } from "./types"
import { generateId } from "./shared"

const healthRecords = new Map<string, ResourceHealth>()

export const ResourceHealthManager = {
  async checkHealth(pool: ResourcePool): Promise<ResourceHealth> {
    const existing = healthRecords.get(pool.id)
    const failureCount = existing?.failureCount ?? 0

    let status: ResourceStatus
    let healthy: boolean
    let message: string

    if (pool.availableCapacity === 0 && pool.totalCapacity > 0) {
      status = "exhausted"
      healthy = false
      message = `Pool ${pool.id} is exhausted: ${pool.allocatedCapacity}/${pool.totalCapacity} allocated`
    } else if (pool.availableCapacity < pool.totalCapacity * 0.1) {
      status = "degraded"
      healthy = true
      message = `Pool ${pool.id} is degraded: ${pool.availableCapacity}/${pool.totalCapacity} remaining`
    } else if (pool.status === "offline") {
      status = "offline"
      healthy = false
      message = `Pool ${pool.id} is offline`
    } else {
      status = "available"
      healthy = true
      message = `Pool ${pool.id} is healthy: ${pool.availableCapacity}/${pool.totalCapacity} available`
    }

    const health: ResourceHealth = {
      poolId: pool.id,
      status,
      healthy,
      lastCheckedAt: new Date().toISOString(),
      failureCount: healthy ? 0 : failureCount + 1,
      lastFailureAt: healthy ? (existing?.lastFailureAt ?? null) : new Date().toISOString(),
      message,
    }

    healthRecords.set(pool.id, health)
    return health
  },

  async getHealth(poolId: string): Promise<ResourceHealth | null> {
    return healthRecords.get(poolId) ?? null
  },

  async getAllHealth(): Promise<ResourceHealth[]> {
    return Array.from(healthRecords.values())
  },

  async getHealthyPoolCount(): Promise<number> {
    return Array.from(healthRecords.values()).filter((h) => h.healthy).length
  },

  async getDegradedPoolCount(): Promise<number> {
    return Array.from(healthRecords.values()).filter((h) => h.status === "degraded").length
  },

  async getExhaustedPoolCount(): Promise<number> {
    return Array.from(healthRecords.values()).filter((h) => h.status === "exhausted").length
  },
}
