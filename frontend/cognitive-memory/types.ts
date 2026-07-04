export type MemoryType = "working" | "episodic" | "semantic" | "procedural"

export type MemoryState = "active" | "archived" | "expired" | "deleted"

export type MemoryPriority = "critical" | "high" | "medium" | "low"

export type MemoryScope = "session" | "user" | "organization" | "global"

export type AssociationType =
  | "same_session"
  | "same_user"
  | "same_objective"
  | "same_capability"
  | "temporal"
  | "causal"
  | "semantic_category"
  | "sequential"
  | "hierarchical"
  | "referenced_by"

export type RecallStrategy =
  | "exact"
  | "recent"
  | "prioritized"
  | "contextual"
  | "associative"
  | "temporal_range"

export type MemoryRelationshipType =
  | "depends_on"
  | "extends"
  | "supersedes"
  | "references"
  | "composed_of"
  | "derived_from"

export type MemorySessionStatus = "active" | "closed" | "expired"

export type MemoryHealthStatus = "healthy" | "degraded" | "unhealthy" | "unknown"

export interface MemorySession {
  id: string
  contextId: string
  userId: string | null
  organizationId: string | null
  status: MemorySessionStatus
  scope: MemoryScope
  createdAt: string
  updatedAt: string
  closedAt: string | null
  entryCount: number
}

export interface MemoryEntryBase {
  id: string
  sessionId: string
  type: MemoryType
  state: MemoryState
  priority: MemoryPriority
  scope: MemoryScope
  tags: string[]
  metadata: Record<string, string>
  createdAt: string
  updatedAt: string
  expiresAt: string | null
}

export interface WorkingMemoryEntry extends MemoryEntryBase {
  type: "working"
  key: string
  value: unknown
  ttl: number
}

export interface EpisodicMemoryEntry extends MemoryEntryBase {
  type: "episodic"
  missionId: string
  episodeNumber: number
  summary: string
  events: MemoryEpisodeEvent[]
  durationMs: number
  outcome: string | null
  linkedEpisodeIds: string[]
}

export interface MemoryEpisodeEvent {
  id: string
  timestamp: string
  type: string
  description: string
  data: Record<string, unknown>
}

export interface SemanticMemoryEntry extends MemoryEntryBase {
  type: "semantic"
  concept: string
  definition: string
  category: string
  aliases: string[]
  relationships: MemoryRelationship[]
  confidence: number
}

export interface MemoryRelationship {
  targetId: string
  type: MemoryRelationshipType
  description: string
  createdAt: string
}

export interface ProceduralMemoryEntry extends MemoryEntryBase {
  type: "procedural"
  procedureName: string
  procedureType: string
  steps: MemoryProcedureStep[]
  inputs: string[]
  outputs: string[]
  conditions: string[]
  version: string
}

export interface MemoryProcedureStep {
  id: string
  order: number
  name: string
  description: string
  action: string
  expectedOutcome: string
  timeoutMs: number
  required: boolean
}

export interface MemoryAssociation {
  id: string
  sourceId: string
  targetId: string
  type: AssociationType
  strength: number
  metadata: Record<string, string>
  createdAt: string
}

export interface MemoryGraphNode {
  id: string
  entryId: string
  type: MemoryType
  label: string
  properties: Record<string, string>
}

export interface MemoryGraphEdge {
  id: string
  sourceNodeId: string
  targetNodeId: string
  relationship: MemoryRelationshipType
  weight: number
  createdAt: string
}

export interface MemoryCluster {
  id: string
  label: string
  nodeIds: string[]
  centerNodeId: string | null
  density: number
  createdAt: string
}

export interface MemorySnapshot {
  id: string
  sessionId: string
  workingEntries: string[]
  episodicEntries: string[]
  semanticEntries: string[]
  proceduralEntries: string[]
  graphNodes: string[]
  graphEdges: string[]
  associations: string[]
  capturedAt: string
}

export interface MemoryTimeline {
  sessionId: string
  entries: Array<{
    entryId: string
    type: MemoryType
    timestamp: string
    summary: string
  }>
  totalEntries: number
  timeRangeMs: number
}

export interface MemoryRecallRequest {
  sessionId: string
  query: string
  types: MemoryType[]
  strategy: RecallStrategy
  maxResults: number
  minConfidence: number
  scope: MemoryScope
  timeRangeMs: number | null
}

export interface MemoryRecallResult {
  request: MemoryRecallRequest
  entries: MemoryEntryBase[]
  totalMatches: number
  returnedCount: number
  durationMs: number
  associations: MemoryAssociation[]
}

export interface MemoryPolicy {
  id: string
  name: string
  description: string
  category: "retention" | "expiration" | "visibility" | "ownership" | "sensitivity" | "confidence" | "access_scope"
  effect: "allow" | "deny" | "audit"
  rules: MemoryPolicyRule[]
  priority: number
  enabled: boolean
}

export interface MemoryPolicyRule {
  field: string
  operator: "eq" | "neq" | "gt" | "gte" | "lt" | "lte" | "in" | "not_in" | "exists" | "not_exists" | "matches"
  value: unknown
  message: string
}

export interface MemoryMetrics {
  systemId: string
  totalEntries: number
  workingCount: number
  episodicCount: number
  semanticCount: number
  proceduralCount: number
  totalAssociations: number
  graphNodes: number
  graphEdges: number
  graphDensity: number
  activeSessions: number
  totalSnapshots: number
  totalRecalls: number
  averageRecallDurationMs: number
  expiredEntries: number
  orphanNodes: number
  memoryGrowthBytes: number
  collectedAt: string
}

export interface MemoryHealth {
  systemId: string
  status: MemoryHealthStatus
  totalEntries: number
  activeEntries: number
  expiredEntries: number
  orphanNodes: number
  brokenEdges: number
  graphConsistent: boolean
  expirationBacklog: number
  recoveryReady: boolean
  message: string
  timestamp: string
}

export interface MemoryConfiguration {
  maxWorkingEntriesPerSession: number
  maxEpisodicEntriesPerSession: number
  maxSemanticEntriesPerSession: number
  maxProceduralEntriesPerSession: number
  defaultWorkingTTL: number
  maxAssociationStrength: number
  enableAutoExpiration: boolean
  enableAutoSnapshot: boolean
  graphTraversalMaxDepth: number
  policies: MemoryPolicy[]
}

export interface MemoryContext {
  sessionId: string
  correlationId: string
  userId: string | null
  organizationId: string | null
  scope: MemoryScope
  metadata: Record<string, string>
}

export type MemoryTaskPayload =
  | { type: "store"; entryType: MemoryType; data: Record<string, unknown> }
  | { type: "recall"; request: MemoryRecallRequest }
  | { type: "associate"; sourceId: string; targetId: string; associationType: AssociationType }
  | { type: "snapshot"; sessionId: string }
  | { type: "expire"; sessionId: string }
  | { type: "link"; parentId: string; childId: string; relationship: MemoryRelationshipType }
  | { type: "traverse"; nodeId: string; depth: number }

export interface RedisConfig {
  host: string
  port: number
  password?: string
  db?: number
  keyPrefix?: string
  connectTimeout?: number
  maxRetriesPerRequest?: number
}

export interface MemorySystemHealth {
  systemId: string
  status: MemoryHealthStatus
  redisConnected: boolean
  redisLatencyMs: number
  totalEntries: number
  activeEntries: number
  expiredEntries: number
  orphanNodes: number
  brokenEdges: number
  graphConsistent: boolean
  expirationBacklog: number
  recoveryReady: boolean
  message: string
  timestamp: string
}
