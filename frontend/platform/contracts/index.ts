export interface PlatformError {
  code: string
  message: string
  module: string
  severity: "critical" | "error" | "warning" | "info"
  timestamp: string
  details: Record<string, unknown> | null
  cause: PlatformError | null
}

export type PlatformCapabilityType =
  | "browser"
  | "voice"
  | "computer_use"
  | "research"
  | "memory"
  | "analytics"
  | "governance"
  | "replay"
  | "integration"
  | "automation"
  | "custom"

export interface PlatformCapability {
  id: string
  name: string
  type: PlatformCapabilityType
  version: string
  features: string[]
  enabled: boolean
}

export interface PlatformContext {
  sessionId: string
  correlationId: string
  userId: string | null
  organizationId: string | null
  metadata: Record<string, string>
  createdAt: string
}

export type PlatformLifecycleState =
  | "created"
  | "initializing"
  | "active"
  | "paused"
  | "suspended"
  | "completed"
  | "failed"
  | "cancelled"

export interface PlatformLifecycle {
  state: PlatformLifecycleState
  transitions: string[]
  startedAt: string
  updatedAt: string
  completedAt: string | null
}

export interface PlatformMetadata {
  key: string
  value: string
  tags: string[]
  createdAt: string
}

export interface PlatformVersion {
  major: number
  minor: number
  patch: number
  label: string | null
  toString(): string
}

export interface PlatformIdentity {
  id: string
  name: string
  type: string
  version: string
  roles: string[]
}
