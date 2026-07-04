export type ResourceStatus = "available" | "degraded" | "exhausted" | "offline"

export interface ResourcePoolConfig {
  resourceType: string
  totalCapacity: number
  quotaPerSession: number
  leaseDurationMs: number
}

export interface ResourceUsage {
  resourceType: string
  allocated: number
  reserved: number
  available: number
  utilizationPercent: number
}

export interface ResourceQuota {
  resourceType: string
  maxAllocation: number
  currentAllocation: number
  remaining: number
}
