export type ResourceType =
  | "cpu"
  | "memory"
  | "gpu"
  | "storage"
  | "network_bandwidth"
  | "concurrent_sessions"
  | "api_quota"
  | "custom"

export type ResourceStatus = "available" | "degraded" | "exhausted" | "offline"

export type LeaseStatus = "active" | "expired" | "released" | "revoked"

export interface ResourceDescriptor {
  id: string
  name: string
  resourceType: ResourceType
  unit: string
  description: string
  metadata: Record<string, string>
}

export interface ResourcePool {
  id: string
  descriptorId: string
  descriptor: ResourceDescriptor
  totalCapacity: number
  allocatedCapacity: number
  reservedCapacity: number
  availableCapacity: number
  status: ResourceStatus
  createdAt: string
  updatedAt: string
}

export interface ResourceLease {
  id: string
  poolId: string
  workerId: string
  sessionId: string
  amount: number
  status: LeaseStatus
  grantedAt: string
  expiresAt: string
  releasedAt: string | null
}

export interface ResourceReservation {
  id: string
  poolId: string
  workerId: string
  sessionId: string
  amount: number
  startAt: string
  endAt: string
  confirmed: boolean
  createdAt: string
}

export interface ResourceAllocation {
  id: string
  poolId: string
  leaseId: string
  workerId: string
  sessionId: string
  amount: number
  allocatedAt: string
  releasedAt: string | null
}

export interface ResourceQuota {
  id: string
  poolId: string
  entityId: string
  entityType: "worker" | "session" | "capability"
  maxAllocation: number
  currentAllocation: number
  peakAllocation: number
}

export interface ResourceUsage {
  poolId: string
  descriptorId: string
  totalAllocated: number
  totalReserved: number
  totalAvailable: number
  utilizationPercent: number
  activeLeases: number
  pendingReservations: number
  recordedAt: string
}

export interface ResourceHealth {
  poolId: string
  status: ResourceStatus
  healthy: boolean
  lastCheckedAt: string
  failureCount: number
  lastFailureAt: string | null
  message: string
}

export interface ResourceMetrics {
  totalPools: number
  totalCapacity: number
  totalAllocated: number
  totalReserved: number
  totalAvailable: number
  overallUtilizationPercent: number
  activeLeases: number
  activeAllocations: number
  pendingReservations: number
  healthyPools: number
  degradedPools: number
  exhaustedPools: number
}
