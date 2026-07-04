import type { PlatformError } from "../contracts"

export type RuntimeStatus = "initializing" | "running" | "degraded" | "stopped" | "error"

export interface RuntimeHealth {
  status: RuntimeStatus
  uptimeMs: number
  activeSessions: number
  activeWorkers: number
  memoryUsage: number
  lastHealthCheck: string
}

export interface RuntimeConfig {
  maxConcurrentSessions: number
  sessionTimeoutMs: number
  heartbeatIntervalMs: number
  enableTelemetry: boolean
  enablePersistence: boolean
}
