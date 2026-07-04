import type { ResourceQuota } from "./types"
import { generateId } from "./shared"

const quotas = new Map<string, ResourceQuota>()

export const QuotaManager = {
  async setQuota(
    poolId: string,
    entityId: string,
    entityType: "worker" | "session" | "capability",
    maxAllocation: number,
  ): Promise<ResourceQuota> {
    const existing = Array.from(quotas.values()).find(
      (q) => q.poolId === poolId && q.entityId === entityId && q.entityType === entityType,
    )

    if (existing) {
      const updated: ResourceQuota = {
        ...existing,
        maxAllocation,
        currentAllocation: Math.min(existing.currentAllocation, maxAllocation),
      }
      quotas.set(existing.id, updated)
      return updated
    }

    const quota: ResourceQuota = {
      id: generateId("quota"),
      poolId,
      entityId,
      entityType,
      maxAllocation,
      currentAllocation: 0,
      peakAllocation: 0,
    }
    quotas.set(quota.id, quota)
    return quota
  },

  async getQuota(poolId: string, entityId: string, entityType: "worker" | "session" | "capability"): Promise<ResourceQuota | null> {
    return Array.from(quotas.values()).find(
      (q) => q.poolId === poolId && q.entityId === entityId && q.entityType === entityType,
    ) ?? null
  },

  async checkQuota(poolId: string, entityId: string, entityType: "worker" | "session" | "capability", requestedAmount: number): Promise<{
    allowed: boolean
    currentAllocation: number
    maxAllocation: number
    remaining: number
  }> {
    const quota = await QuotaManager.getQuota(poolId, entityId, entityType)
    if (!quota) return { allowed: true, currentAllocation: 0, maxAllocation: Infinity, remaining: Infinity }
    const remaining = quota.maxAllocation - quota.currentAllocation
    return {
      allowed: requestedAmount <= remaining,
      currentAllocation: quota.currentAllocation,
      maxAllocation: quota.maxAllocation,
      remaining,
    }
  },

  async recordAllocation(poolId: string, entityId: string, entityType: "worker" | "session" | "capability", amount: number): Promise<ResourceQuota> {
    const quota = await QuotaManager.getQuota(poolId, entityId, entityType)
    if (!quota) throw new Error(`No quota found for ${entityType} ${entityId} in pool ${poolId}`)
    const newAllocation = quota.currentAllocation + amount
    const updated: ResourceQuota = {
      ...quota,
      currentAllocation: newAllocation,
      peakAllocation: Math.max(quota.peakAllocation, newAllocation),
    }
    quotas.set(quota.id, updated)
    return updated
  },

  async recordRelease(poolId: string, entityId: string, entityType: "worker" | "session" | "capability", amount: number): Promise<ResourceQuota> {
    const quota = await QuotaManager.getQuota(poolId, entityId, entityType)
    if (!quota) throw new Error(`No quota found for ${entityType} ${entityId} in pool ${poolId}`)
    const updated: ResourceQuota = {
      ...quota,
      currentAllocation: Math.max(0, quota.currentAllocation - amount),
    }
    quotas.set(quota.id, updated)
    return updated
  },

  async getEntityQuotas(entityId: string): Promise<ResourceQuota[]> {
    return Array.from(quotas.values()).filter((q) => q.entityId === entityId)
  },

  async getAllQuotas(): Promise<ResourceQuota[]> {
    return Array.from(quotas.values())
  },
}
