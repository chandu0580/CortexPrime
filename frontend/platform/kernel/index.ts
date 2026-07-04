import type { PlatformLifecycleState } from "../contracts"

export type KernelMode = "active" | "maintenance" | "readonly" | "shutdown"

export interface KernelConfig {
  mode: KernelMode
  maxSessions: number
  sessionTimeoutMs: number
  enablePersistence: boolean
}

export interface KernelSessionSummary {
  sessionId: string
  state: PlatformLifecycleState
  ageMs: number
  moduleCount: number
}
