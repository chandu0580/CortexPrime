import type { ResourcePool, ResourceDescriptor, ResourceStatus } from "./types"
import { generateId } from "./shared"

const pools = new Map<string, ResourcePool>()

export const ResourcePoolManager = {
  async createPool(descriptor: ResourceDescriptor, totalCapacity: number): Promise<ResourcePool> {
    const pool: ResourcePool = {
      id: generateId("pool"),
      descriptorId: descriptor.id,
      descriptor,
      totalCapacity,
      allocatedCapacity: 0,
      reservedCapacity: 0,
      availableCapacity: totalCapacity,
      status: "available",
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }
    pools.set(pool.id, pool)
    return pool
  },

  async getPool(poolId: string): Promise<ResourcePool | null> {
    return pools.get(poolId) ?? null
  },

  async findPoolsByDescriptor(descriptorId: string): Promise<ResourcePool[]> {
    return Array.from(pools.values()).filter((p) => p.descriptorId === descriptorId)
  },

  async getAllPools(): Promise<ResourcePool[]> {
    return Array.from(pools.values())
  },

  async updatePool(poolId: string, updates: Partial<ResourcePool>): Promise<ResourcePool> {
    const pool = pools.get(poolId)
    if (!pool) throw new Error(`Pool not found: ${poolId}`)
    const updated: ResourcePool = {
      ...pool,
      ...updates,
      availableCapacity: (updates.totalCapacity ?? pool.totalCapacity)
        - (updates.allocatedCapacity ?? pool.allocatedCapacity)
        - (updates.reservedCapacity ?? pool.reservedCapacity),
      updatedAt: new Date().toISOString(),
    }
    pools.set(poolId, updated)
    return updated
  },

  async allocateCapacity(poolId: string, amount: number): Promise<ResourcePool> {
    const pool = pools.get(poolId)
    if (!pool) throw new Error(`Pool not found: ${poolId}`)
    if (pool.availableCapacity < amount) throw new Error(`Insufficient capacity in pool ${poolId}: requested ${amount}, available ${pool.availableCapacity}`)
    return ResourcePoolManager.updatePool(poolId, {
      allocatedCapacity: pool.allocatedCapacity + amount,
    })
  },

  async releaseCapacity(poolId: string, amount: number): Promise<ResourcePool> {
    const pool = pools.get(poolId)
    if (!pool) throw new Error(`Pool not found: ${poolId}`)
    return ResourcePoolManager.updatePool(poolId, {
      allocatedCapacity: Math.max(0, pool.allocatedCapacity - amount),
    })
  },

  async reserveCapacity(poolId: string, amount: number): Promise<ResourcePool> {
    const pool = pools.get(poolId)
    if (!pool) throw new Error(`Pool not found: ${poolId}`)
    if (pool.availableCapacity < amount) throw new Error(`Insufficient capacity for reservation in pool ${poolId}`)
    return ResourcePoolManager.updatePool(poolId, {
      reservedCapacity: pool.reservedCapacity + amount,
    })
  },

  async releaseReservation(poolId: string, amount: number): Promise<ResourcePool> {
    const pool = pools.get(poolId)
    if (!pool) throw new Error(`Pool not found: ${poolId}`)
    return ResourcePoolManager.updatePool(poolId, {
      reservedCapacity: Math.max(0, pool.reservedCapacity - amount),
    })
  },

  async setPoolStatus(poolId: string, status: ResourceStatus): Promise<ResourcePool> {
    return ResourcePoolManager.updatePool(poolId, { status })
  },

  async getPoolCount(): Promise<number> {
    return pools.size
  },
}
