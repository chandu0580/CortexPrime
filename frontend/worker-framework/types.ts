import type { PlatformCapability, PlatformContext } from "@/platform/contracts"

export type WorkerState =
  | "CREATED"
  | "REGISTERED"
  | "INITIALIZED"
  | "READY"
  | "RUNNING"
  | "PAUSED"
  | "STOPPED"
  | "SHUTDOWN"

export type WorkerHealthStatus = "healthy" | "degraded" | "unhealthy" | "unknown"

export interface WorkerDescriptor {
  id: string
  name: string
  type: string
  version: string
  description: string
  capabilities: PlatformCapability[]
  metadata: Record<string, string>
}

export interface WorkerCapability {
  descriptorId: string
  capability: PlatformCapability
  confidence: number
  available: boolean
}

export interface WorkerConfiguration {
  maxConcurrentTasks: number
  heartbeatIntervalMs: number
  healthCheckIntervalMs: number
  taskTimeoutMs: number
  autoRecovery: boolean
  maxRetries: number
  settings: Record<string, unknown>
}

export interface WorkerContext {
  currentSessionId: string | null
  currentTaskId: string | null
  platformContext: PlatformContext | null
  startedAt: string | null
  lastActivityAt: string | null
}

export interface WorkerHeartbeat {
  workerId: string
  timestamp: string
  status: WorkerState
  currentTaskId: string | null
  memoryUsage: number
  cpuUsage: number
  healthy: boolean
}

export interface WorkerHealth {
  workerId: string
  status: WorkerHealthStatus
  lastHeartbeatAt: string | null
  lastHealthCheckAt: string
  consecutiveFailures: number
  errorCount: number
  message: string
}

export interface WorkerLifecycle {
  state: WorkerState
  previousState: WorkerState | null
  transitions: string[]
  startedAt: string
  updatedAt: string
  completedAt: string | null
}

export interface WorkerMetrics {
  workerId: string
  uptimeMs: number
  tasksCompleted: number
  tasksFailed: number
  tasksRunning: number
  totalHeartbeats: number
  averageTaskDurationMs: number
  errorRate: number
  lastMetricAt: string
}

export interface WorkerRegistration {
  workerId: string
  descriptor: WorkerDescriptor
  state: WorkerState
  registeredAt: string
  lastSeenAt: string
  healthy: boolean
}
