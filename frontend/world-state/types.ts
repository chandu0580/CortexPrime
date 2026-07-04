export type StateStatus = "active" | "inactive" | "archived" | "deleted"

export type StateTransitionStatus = "pending" | "committed" | "rolled_back" | "failed"

export type StateConflictSeverity = "critical" | "major" | "minor" | "none"

export type StateScope = "global" | "domain" | "session" | "worker" | "capability"

export type StateSynchronizationStrategy = "full" | "incremental" | "selective"

export type StateHealthStatus = "healthy" | "degraded" | "unhealthy" | "unknown"

export type StateChangeType = "create" | "update" | "remove" | "merge"

export interface WorldState {
  id: string
  name: string
  version: string
  entries: Record<string, StateEntry>
  registeredTypes: string[]
  scopes: StateScope[]
  createdAt: string
  updatedAt: string
  entryCount: number
}

export interface StateEntry {
  id: string
  key: string
  value: unknown
  type: string
  status: StateStatus
  scope: StateScope
  domain: string
  owner: string
  version: number
  tags: string[]
  metadata: Record<string, string>
  references: StateReference[]
  createdAt: string
  updatedAt: string
  expiresAt: string | null
}

export interface StateReference {
  targetKey: string
  targetDomain: string
  relationship: string
  required: boolean
}

export interface StateSnapshot {
  id: string
  label: string
  entries: Record<string, unknown>
  entryKeys: string[]
  metadata: Record<string, string>
  capturedAt: string
  version: string
}

export interface StateTransition {
  id: string
  entryKey: string
  from: unknown
  to: unknown
  type: StateChangeType
  status: StateTransitionStatus
  actor: string
  reason: string
  metadata: Record<string, string>
  timestamp: string
  durationMs: number
}

export interface StateRegistryEntry {
  id: string
  key: string
  type: string
  domain: string
  scope: StateScope
  status: StateStatus
  schema: Record<string, unknown>
  registeredAt: string
  updatedAt: string
}

export interface StateChange {
  entryKey: string
  type: StateChangeType
  previousValue: unknown
  newValue: unknown
  timestamp: string
}

export interface StateContext {
  sessionId: string
  actor: string
  scope: StateScope
  domain: string
  metadata: Record<string, string>
}

export interface StateValidation {
  valid: boolean
  totalEntries: number
  activeEntries: number
  conflicts: StateConflict[]
  missingReferences: string[]
  invalidReferences: string[]
  expiredEntries: number
  consistencyScore: number
  validatedAt: string
}

export interface StateConflict {
  id: string
  entryKey: string
  domain: string
  severity: StateConflictSeverity
  description: string
  conflictingValues: Record<string, unknown>[]
  detectedAt: string
}

export interface StateResolution {
  id: string
  conflictId: string
  entryKey: string
  resolution: string
  resolvedValue: unknown
  resolvedBy: string
  resolvedAt: string
}

export interface StateSynchronization {
  id: string
  strategy: StateSynchronizationStrategy
  sourceScope: StateScope
  targetScope: StateScope
  entriesSynchronized: number
  conflictsDetected: number
  conflictsResolved: number
  durationMs: number
  timestamp: string
}

export interface StatePolicy {
  id: string
  name: string
  description: string
  category: "ownership" | "visibility" | "consistency" | "expiration" | "authority" | "synchronization" | "priority"
  effect: "allow" | "deny" | "audit"
  rules: StatePolicyRule[]
  priority: number
  enabled: boolean
}

export interface StatePolicyRule {
  field: string
  operator: "eq" | "neq" | "gt" | "gte" | "lt" | "lte" | "in" | "not_in" | "exists" | "not_exists" | "matches"
  value: unknown
  message: string
}

export interface StateMetrics {
  systemId: string
  totalEntries: number
  activeEntries: number
  archivedEntries: number
  deletedEntries: number
  totalTransitions: number
  totalSnapshots: number
  totalSynchronizations: number
  totalValidations: number
  totalConflicts: number
  totalResolutions: number
  registeredTypes: number
  consistencyScore: number
  avgTransitionDurationMs: number
  avgSyncDurationMs: number
  staleEntries: number
  collectedAt: string
}

export interface StateHealth {
  systemId: string
  status: StateHealthStatus
  consistencyScore: number
  staleEntries: number
  orphanEntries: number
  invalidReferences: number
  conflictCount: number
  synchronizationBacklog: number
  recoveryReady: boolean
  message: string
  timestamp: string
}

export interface StateTimeline {
  systemId: string
  entries: Array<{
    entryKey: string
    type: StateChangeType
    timestamp: string
    actor: string
    summary: string
  }>
  totalChanges: number
  timeRangeMs: number
}

export interface StateVersion {
  major: number
  minor: number
  patch: number
  label: string
}

export interface StateDiff {
  entryKey: string
  from: unknown
  to: unknown
  changed: boolean
}

export interface WorldStateRequest {
  type: "create" | "update" | "remove" | "query" | "snapshot" | "synchronize" | "validate"
  key?: string
  value?: unknown
  domain?: string
  scope?: StateScope
  actor: string
  metadata?: Record<string, string>
}

export interface StateConfiguration {
  maxEntries: number
  maxSnapshotHistory: number
  autoSnapshotIntervalMs: number
  enableAutoValidation: boolean
  enableConflictDetection: boolean
  defaultScope: StateScope
  syncStrategy: StateSynchronizationStrategy
  policies: StatePolicy[]
}
