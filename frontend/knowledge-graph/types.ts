export type EntityStatus = "active" | "inactive" | "archived" | "merged"

export type EntityCategory =
  | "concept"
  | "agent"
  | "capability"
  | "memory"
  | "mission"
  | "worker"
  | "evidence"
  | "procedure"
  | "state"
  | "intelligence"
  | "voice"
  | "browser"
  | "custom"

export type RelationshipType =
  | "depends_on"
  | "composed_of"
  | "derived_from"
  | "references"
  | "supersedes"
  | "equivalent_to"
  | "causes"
  | "enables"
  | "constrains"
  | "relates_to"
  | "same_as"
  | "part_of"
  | "used_by"
  | "implements"
  | "extends"

export type InferenceType =
  | "transitive"
  | "symmetric"
  | "reflexive"
  | "compositional"
  | "hierarchical"
  | "categorical"
  | "redundancy"

export type TraversalStrategy = "bfs" | "dfs" | "shortest_path" | "all_paths"

export type GraphHealthStatus = "healthy" | "degraded" | "unhealthy" | "unknown"

export interface KnowledgeEntity {
  id: string
  name: string
  type: string
  category: EntityCategory
  status: EntityStatus
  description: string
  properties: Record<string, unknown>
  tags: string[]
  source: string
  confidence: number
  aliases: string[]
  createdAt: string
  updatedAt: string
}

export interface KnowledgeRelationship {
  id: string
  sourceId: string
  targetId: string
  type: RelationshipType
  weight: number
  confidence: number
  properties: Record<string, string>
  bidirectional: boolean
  createdAt: string
  updatedAt: string
}

export interface GraphNode {
  id: string
  entityId: string
  label: string
  category: EntityCategory
  properties: Record<string, string>
}

export interface GraphEdge {
  id: string
  sourceNodeId: string
  targetNodeId: string
  relationshipId: string
  type: RelationshipType
  weight: number
}

export interface GraphPath {
  nodes: GraphNode[]
  edges: GraphEdge[]
  totalWeight: number
  nodeCount: number
  edgeCount: number
}

export interface GraphTraversal {
  strategy: TraversalStrategy
  startNodeId: string
  maxDepth: number
  paths: GraphPath[]
  visitedNodes: string[]
  visitedEdges: string[]
  durationMs: number
}

export interface GraphNeighborhood {
  centerNode: GraphNode
  nodes: GraphNode[]
  edges: GraphEdge[]
  depth: number
  nodeCount: number
  edgeCount: number
}

export interface KnowledgeCluster {
  id: string
  label: string
  entityIds: string[]
  centralEntityId: string | null
  density: number
  memberCount: number
  createdAt: string
}

export interface KnowledgeContext {
  sessionId: string
  actor: string
  domain: string
  metadata: Record<string, string>
}

export interface KnowledgeEvidence {
  id: string
  entityId: string
  source: string
  content: string
  confidence: number
  timestamp: string
}

export interface KnowledgeFact {
  id: string
  subjectId: string
  predicate: string
  objectId: string
  confidence: number
  source: string
  timestamp: string
}

export interface KnowledgeInference {
  id: string
  type: InferenceType
  sourceRelationships: string[]
  inferredRelationship: KnowledgeRelationship
  confidence: number
  rationale: string
  createdAt: string
}

export interface GraphSnapshot {
  id: string
  label: string
  nodeCount: number
  edgeCount: number
  entityCount: number
  capturedAt: string
}

export interface GraphDiff {
  addedNodes: string[]
  removedNodes: string[]
  addedEdges: string[]
  removedEdges: string[]
  changedEntities: string[]
}

export interface GraphPolicy {
  id: string
  name: string
  description: string
  category: "visibility" | "ownership" | "confidence" | "relationship" | "uniqueness" | "integrity"
  effect: "allow" | "deny" | "audit"
  rules: GraphPolicyRule[]
  priority: number
  enabled: boolean
}

export interface GraphPolicyRule {
  field: string
  operator: "eq" | "neq" | "gt" | "gte" | "lt" | "lte" | "in" | "not_in" | "exists" | "not_exists" | "matches"
  value: unknown
  message: string
}

export interface GraphMetrics {
  systemId: string
  totalEntities: number
  activeEntities: number
  totalRelationships: number
  graphNodes: number
  graphEdges: number
  graphDensity: number
  connectedComponents: number
  totalTraversals: number
  totalInferences: number
  totalValidations: number
  totalClusters: number
  avgConfidence: number
  duplicateEntities: number
  orphanNodes: number
  collectedAt: string
}

export interface GraphHealth {
  systemId: string
  status: GraphHealthStatus
  totalEntities: number
  totalRelationships: number
  orphanNodes: number
  invalidEdges: number
  duplicateEntities: number
  disconnectedComponents: number
  consistencyScore: number
  recoveryReady: boolean
  message: string
  timestamp: string
}

export interface EntityReference {
  entityId: string
  name: string
  category: EntityCategory
  relationship: RelationshipType
}

export interface RelationshipReference {
  relationshipId: string
  sourceId: string
  targetId: string
  type: RelationshipType
}

export interface KnowledgeRequest {
  type: "register_entity" | "create_relationship" | "traverse" | "infer" | "validate" | "query_entity" | "query_relationship"
  entity?: Omit<KnowledgeEntity, "id" | "createdAt" | "updatedAt">
  relationship?: Omit<KnowledgeRelationship, "id" | "createdAt" | "updatedAt">
  traversal?: { startEntityId: string; strategy: TraversalStrategy; maxDepth: number }
  query?: { field: string; value: string }
  actor: string
  metadata?: Record<string, string>
}

export interface KnowledgeResult {
  success: boolean
  data: unknown
  error: string | null
  durationMs: number
  timestamp: string
}

export interface GraphConfiguration {
  maxEntities: number
  maxRelationships: number
  maxTraversalDepth: number
  enableAutoInference: boolean
  enableCycleDetection: boolean
  defaultConfidence: number
  policies: GraphPolicy[]
}

export interface Neo4jConfig {
  uri: string
  username: string
  password: string
  database?: string
  encrypted?: boolean
  trust?: "TRUST_ALL_CERTIFICATES" | "TRUST_SYSTEM_CA_SIGNED_CERTIFICATES"
  maxConnectionPoolSize?: number
  connectionAcquisitionTimeout?: number
  maxTransactionRetryTime?: number
}

export interface KnowledgeSystemHealth {
  systemId: string
  status: GraphHealthStatus
  neo4jConnected: boolean
  neo4jLatencyMs: number
  totalEntities: number
  totalRelationships: number
  orphanNodes: number
  invalidEdges: number
  duplicateEntities: number
  disconnectedComponents: number
  consistencyScore: number
  recoveryReady: boolean
  message: string
  timestamp: string
}
