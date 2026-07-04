import type { ResourcePool, ResourceLease, ResourceAllocation } from "./types"
import { ResourcePoolManager } from "./ResourcePoolManager"
import { LeaseManager } from "./LeaseManager"
import { AllocationEngine } from "./AllocationEngine"

export const CleanupCoordinator = {
  async runCleanup(): Promise<{
    expiredLeases: ResourceLease[]
    releasedCapacity: number
    poolsUpdated: number
  }> {
    const expiredLeases = await LeaseManager.expireLeases()
    let releasedCapacity = 0
    const poolsToUpdate = new Set<string>()

    for (const lease of expiredLeases) {
      const allocations = await AllocationEngine.getWorkerAllocations(lease.workerId)
      for (const allocation of allocations) {
        if (allocation.leaseId === lease.id && allocation.releasedAt === null) {
          await AllocationEngine.release(allocation.id)
          releasedCapacity += allocation.amount
          poolsToUpdate.add(allocation.poolId)
        }
      }
    }

    return {
      expiredLeases,
      releasedCapacity,
      poolsUpdated: poolsToUpdate.size,
    }
  },

  async cleanupSession(sessionId: string): Promise<{
    leasesReleased: number
    allocationsReleased: number
    capacityReleased: number
  }> {
    const sessionLeases = await LeaseManager.getSessionLeases(sessionId)
    const sessionAllocations = await AllocationEngine.getSessionAllocations(sessionId)
    let capacityReleased = 0

    for (const allocation of sessionAllocations) {
      if (allocation.releasedAt === null) {
        await AllocationEngine.release(allocation.id)
        capacityReleased += allocation.amount
      }
    }

    for (const lease of sessionLeases) {
      if (lease.status === "active") {
        await LeaseManager.releaseLease(lease.id)
      }
    }

    return {
      leasesReleased: sessionLeases.filter((l) => l.status === "active").length,
      allocationsReleased: sessionAllocations.filter((a) => a.releasedAt === null).length,
      capacityReleased,
    }
  },
}
