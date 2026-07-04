import type { PlatformContext } from "../contracts"

export type ContextScope = "session" | "pipeline" | "task" | "worker"

export type ContextAccess = "read" | "write" | "admin"

export interface ContextPermission {
  scope: ContextScope
  access: ContextAccess
  resourceId: string
}

export interface ContextSnapshot {
  context: PlatformContext
  permissions: ContextPermission[]
  capturedAt: string
}

export interface ContextDiff {
  field: string
  previousValue: unknown
  newValue: unknown
}
