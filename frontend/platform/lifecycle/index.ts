import type { PlatformLifecycleState } from "../contracts"

export interface LifecycleTransition {
  fromState: PlatformLifecycleState
  toState: PlatformLifecycleState
  valid: boolean
}

export interface LifecycleHook {
  hookId: string
  onState: PlatformLifecycleState
  action: "notify" | "log" | "validate" | "callback"
  handlerId: string | null
}

export const LIFECYCLE_TRANSITIONS: Record<PlatformLifecycleState, PlatformLifecycleState[]> = {
  created: ["initializing"],
  initializing: ["active", "failed"],
  active: ["paused", "completed", "failed", "cancelled"],
  paused: ["active", "suspended", "cancelled"],
  suspended: ["active", "cancelled"],
  completed: [],
  failed: ["initializing"],
  cancelled: [],
}
