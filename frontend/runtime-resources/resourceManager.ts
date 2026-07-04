import type { ResourceType, ResourceAllocation, ResourcePool, ResourceLease, ResourceReservation, ResourceMetrics } from "./types"
import type { ResourceDescriptor } from "./types"
import { ResourceCatalog } from "./ResourceCatalog"
import { ResourcePoolManager } from "./ResourcePoolManager"
import { LeaseManager } from "./LeaseManager"
import { ReservationManager } from "./ReservationManager"
import { QuotaManager } from "./QuotaManager"
import { AllocationEngine } from "./AllocationEngine"
import { ResourceHealthManager } from "./ResourceHealthManager"
import { CleanupCoordinator } from "./CleanupCoordinator"

export const resourceManager = {
  async registerResource(
    name: string,
    resourceType: ResourceType,
    unit: string,
    description: string,
    metadata?: Record<string, string>,
  ): Promise<ResourceDescriptor> {
    return ResourceCatalog.registerResource(name, resourceType, unit, description, metadata)
  },

  async createPool(descriptorId: string, totalCapacity: number): Promise<ResourcePool> {
    const descriptor = await ResourceCatalog.getDescriptor(descriptorId)
    if (!descriptor) throw new Error(`Descriptor not found: ${descriptorId}`)
    return ResourcePoolManager.createPool(descriptor, totalCapacity)
  },

  async reserve(
    poolId: string,
    workerId: string,
    sessionId: string,
    amount: number,
    startAt: string,
    endAt: string,
  ): Promise<{ reservation: ResourceReservation; pool: ResourcePool }> {
    const pool = await ResourcePoolManager.reserveCapacity(poolId, amount)
    const reservation = await ReservationManager.createReservation(poolId, workerId, sessionId, amount, startAt, endAt)
    return { reservation, pool }
  },

  async allocate(
    poolId: string,
    workerId: string,
    sessionId: string,
    amount: number,
    leaseDurationMs?: number,
  ): Promise<{ allocation: ResourceAllocation; pool: ResourcePool }> {
    return AllocationEngine.allocate(poolId, workerId, sessionId, amount, "session", leaseDurationMs)
  },

  async lease(
    poolId: string,
    workerId: string,
    sessionId: string,
    amount: number,
    durationMs?: number,
  ): Promise<ResourceLease> {
    return LeaseManager.grantLease(poolId, workerId, sessionId, amount, durationMs)
  },

  async release(allocationId: string): Promise<{ allocation: ResourceAllocation; pool: ResourcePool }> {
    const result = await AllocationEngine.release(allocationId)

    const pool = await ResourcePoolManager.getPool(result.pool.id)
    if (pool) {
      await ResourceHealthManager.checkHealth(pool)
    }

    return result
  },

  async cleanup(): Promise<{ expiredLeases: ResourceLease[]; releasedCapacity: number }> {
    const result = await CleanupCoordinator.runCleanup()

    const pools = await ResourcePoolManager.getAllPools()
    for (const pool of pools) {
      await ResourceHealthManager.checkHealth(pool)
    }

    return { expiredLeases: result.expiredLeases, releasedCapacity: result.releasedCapacity }
  },

  async reportUsage(): Promise<ResourceMetrics> {
    const pools = await ResourcePoolManager.getAllPools()
    const activeLeases = await LeaseManager.getActiveLeaseCount()
    const activeAllocations = await AllocationEngine.getActiveAllocationCount()
    const reservations = await ReservationManager.getActiveReservationCount()

    let totalCapacity = 0
    let totalAllocated = 0
    let totalReserved = 0

    for (const pool of pools) {
      totalCapacity += pool.totalCapacity
      totalAllocated += pool.allocatedCapacity
      totalReserved += pool.reservedCapacity
    }

    const totalAvailable = totalCapacity - totalAllocated - totalReserved
    const overallUtilizationPercent = totalCapacity > 0 ? ((totalAllocated + totalReserved) / totalCapacity) * 100 : 0
    const healthyPools = await ResourceHealthManager.getHealthyPoolCount()
    const degradedPools = await ResourceHealthManager.getDegradedPoolCount()
    const exhaustedPools = await ResourceHealthManager.getExhaustedPoolCount()

    return {
      totalPools: pools.length,
      totalCapacity,
      totalAllocated,
      totalReserved,
      totalAvailable,
      overallUtilizationPercent,
      activeLeases,
      activeAllocations,
      pendingReservations: reservations,
      healthyPools,
      degradedPools,
      exhaustedPools,
    }
  },
}
