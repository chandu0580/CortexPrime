import type { ResourceAllocation, ResourcePool } from "./types"
import { ResourcePoolManager } from "./ResourcePoolManager"
import { LeaseManager } from "./LeaseManager"
import { QuotaManager } from "./QuotaManager"
import { generateId } from "./shared"

const allocations = new Map<string, ResourceAllocation>()

export const AllocationEngine = {
  async allocate(
    poolId: string,
    workerId: string,
    sessionId: string,
    amount: number,
    entityType: "worker" | "session" | "capability" = "session",
    leaseDurationMs: number = 300000,
  ): Promise<{
    allocation: ResourceAllocation
    pool: ResourcePool
  }> {
    const pool = await ResourcePoolManager.getPool(poolId)
    if (!pool) throw new Error(`Pool not found: ${poolId}`)

    if (pool.availableCapacity < amount) {
      throw new Error(`Insufficient capacity: requested ${amount}, available ${pool.availableCapacity}`)
    }

    const quotaCheck = await QuotaManager.checkQuota(poolId, sessionId, entityType, amount)
    if (!quotaCheck.allowed) {
      throw new Error(`Quota exceeded: requested ${amount}, remaining ${quotaCheck.remaining}`)
    }

    const lease = await LeaseManager.grantLease(poolId, workerId, sessionId, amount, leaseDurationMs)
    const updatedPool = await ResourcePoolManager.allocateCapacity(poolId, amount)
    await QuotaManager.recordAllocation(poolId, sessionId, entityType, amount)

    const allocation: ResourceAllocation = {
      id: generateId("allocation"),
      poolId,
      leaseId: lease.id,
      workerId,
      sessionId,
      amount,
      allocatedAt: new Date().toISOString(),
      releasedAt: null,
    }
    allocations.set(allocation.id, allocation)

    return { allocation, pool: updatedPool }
  },

  async release(allocationId: string): Promise<{
    allocation: ResourceAllocation
    pool: ResourcePool
  }> {
    const allocation = allocations.get(allocationId)
    if (!allocation) throw new Error(`Allocation not found: ${allocationId}`)

    await LeaseManager.releaseLease(allocation.leaseId)
    const updatedPool = await ResourcePoolManager.releaseCapacity(allocation.poolId, allocation.amount)
    await QuotaManager.recordRelease(allocation.poolId, allocation.sessionId, "session", allocation.amount)

    const updated: ResourceAllocation = {
      ...allocation,
      releasedAt: new Date().toISOString(),
    }
    allocations.set(allocationId, updated)

    return { allocation: updated, pool: updatedPool }
  },

  async getAllocation(id: string): Promise<ResourceAllocation | null> {
    return allocations.get(id) ?? null
  },

  async getSessionAllocations(sessionId: string): Promise<ResourceAllocation[]> {
    return Array.from(allocations.values()).filter((a) => a.sessionId === sessionId)
  },

  async getWorkerAllocations(workerId: string): Promise<ResourceAllocation[]> {
    return Array.from(allocations.values()).filter((a) => a.workerId === workerId)
  },

  async getActiveAllocations(): Promise<ResourceAllocation[]> {
    return Array.from(allocations.values()).filter((a) => a.releasedAt === null)
  },

  async getActiveAllocationCount(): Promise<number> {
    return (await AllocationEngine.getActiveAllocations()).length
  },
}
