import type { ResourceLease, LeaseStatus } from "./types"
import { generateId } from "./shared"

const leases = new Map<string, ResourceLease>()

export const LeaseManager = {
  async grantLease(
    poolId: string,
    workerId: string,
    sessionId: string,
    amount: number,
    durationMs: number = 300000,
  ): Promise<ResourceLease> {
    const lease: ResourceLease = {
      id: generateId("lease"),
      poolId,
      workerId,
      sessionId,
      amount,
      status: "active",
      grantedAt: new Date().toISOString(),
      expiresAt: new Date(Date.now() + durationMs).toISOString(),
      releasedAt: null,
    }
    leases.set(lease.id, lease)
    return lease
  },

  async getLease(leaseId: string): Promise<ResourceLease | null> {
    return leases.get(leaseId) ?? null
  },

  async releaseLease(leaseId: string): Promise<ResourceLease> {
    const lease = leases.get(leaseId)
    if (!lease) throw new Error(`Lease not found: ${leaseId}`)
    const updated: ResourceLease = {
      ...lease,
      status: "released",
      releasedAt: new Date().toISOString(),
    }
    leases.set(leaseId, updated)
    return updated
  },

  async revokeLease(leaseId: string): Promise<ResourceLease> {
    const lease = leases.get(leaseId)
    if (!lease) throw new Error(`Lease not found: ${leaseId}`)
    const updated: ResourceLease = {
      ...lease,
      status: "revoked",
      releasedAt: new Date().toISOString(),
    }
    leases.set(leaseId, updated)
    return updated
  },

  async expireLeases(): Promise<ResourceLease[]> {
    const now = new Date()
    const expired: ResourceLease[] = []

    for (const [id, lease] of leases) {
      if (lease.status === "active" && new Date(lease.expiresAt) < now) {
        const updated: ResourceLease = { ...lease, status: "expired" }
        leases.set(id, updated)
        expired.push(updated)
      }
    }

    return expired
  },

  async getSessionLeases(sessionId: string): Promise<ResourceLease[]> {
    return Array.from(leases.values()).filter((l) => l.sessionId === sessionId)
  },

  async getWorkerLeases(workerId: string): Promise<ResourceLease[]> {
    return Array.from(leases.values()).filter((l) => l.workerId === workerId)
  },

  async getActiveLeases(): Promise<ResourceLease[]> {
    return Array.from(leases.values()).filter((l) => l.status === "active")
  },

  async getActiveLeaseCount(): Promise<number> {
    return (await LeaseManager.getActiveLeases()).length
  },

  async isExpired(leaseId: string): Promise<boolean> {
    const lease = leases.get(leaseId)
    if (!lease) return true
    return new Date(lease.expiresAt) < new Date()
  },
}
