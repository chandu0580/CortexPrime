import type { PlatformError } from "@/platform/contracts"

export type IntelligenceState =
  | "idle"
  | "planning"
  | "collecting"
  | "analyzing"
  | "generating"
  | "summarizing"
  | "completed"
  | "error"

export type IntelligenceSessionStatus =
  | "created"
  | "active"
  | "paused"
  | "completed"
  | "failed"
  | "cancelled"

export type IntelligencePlanStatus =
  | "draft"
  | "active"
  | "completed"
  | "failed"
  | "cancelled"

export type IntelligenceStageStatus =
  | "pending"
  | "in_progress"
  | "completed"
  | "failed"
  | "skipped"

export type EvidenceCategory =
  | "document"
  | "market"
  | "competitive"
  | "financial"
  | "regulatory"
  | "technical"
  | "operational"
  | "strategic"

export type EvidenceConfidence = "high" | "medium" | "low" | "unverified"

export type EvidenceRelationshipType = "supports" | "contradicts" | "corroborates" | "extends" | "supersedes"

export type InsightPriority = "critical" | "high" | "medium" | "low"

export type RecommendationPriority = "critical" | "high" | "medium" | "low"

export type RecommendationStatus =
  | "proposed"
  | "accepted"
  | "rejected"
  | "implemented"
  | "deferred"

export type IntelligenceActivityType =
  | "session_created"
  | "plan_created"
  | "objective_added"
  | "stage_completed"
  | "evidence_added"
  | "evidence_validated"
  | "insight_generated"
  | "recommendation_created"
  | "summary_completed"
  | "policy_evaluated"
  | "session_closed"

export type IntelligenceRequestType =
  | "research"
  | "analysis"
  | "competitive_intel"
  | "market_intel"
  | "document_intel"
  | "policy_intel"
  | "executive_intel"
  | "knowledge_analysis"

export type IntelligencePolicyEffect = "allow" | "deny" | "audit"

export interface IntelligenceSession {
  id: string
  status: IntelligenceSessionStatus
  state: IntelligenceState
  request: IntelligenceRequest
  planId: string | null
  summaryId: string | null
  startedAt: string
  updatedAt: string
  completedAt: string | null
  error: PlatformError | null
}

export interface IntelligenceRequest {
  id: string
  type: IntelligenceRequestType
  query: string
  context: Record<string, string>
  constraints: string[]
  priority: InsightPriority
  requestedAt: string
}

export interface IntelligenceObjective {
  id: string
  planId: string
  description: string
  key: string
  target: string
  completed: boolean
  completedAt: string | null
}

export interface IntelligencePlan {
  id: string
  sessionId: string
  status: IntelligencePlanStatus
  objectives: IntelligenceObjective[]
  stages: IntelligenceStage[]
  progress: number
  createdAt: string
  updatedAt: string
  completedAt: string | null
}

export interface IntelligenceStage {
  id: string
  planId: string
  name: string
  description: string
  order: number
  status: IntelligenceStageStatus
  startedAt: string | null
  completedAt: string | null
  durationMs: number | null
}

export interface Evidence {
  id: string
  sessionId: string
  sourceId: string
  category: EvidenceCategory
  confidence: EvidenceConfidence
  confidenceScore: number
  content: string
  metadata: Record<string, string>
  relationships: EvidenceRelationship[]
  validated: boolean
  validationErrors: string[]
  duplicateOf: string | null
  createdAt: string
}

export interface EvidenceCollection {
  id: string
  sessionId: string
  evidenceIds: string[]
  collectedAt: string
  totalCount: number
  categories: EvidenceCategory[]
}

export interface EvidenceRelationship {
  sourceId: string
  targetId: string
  type: EvidenceRelationshipType
  description: string
  createdAt: string
}

export interface Insight {
  id: string
  sessionId: string
  evidenceIds: string[]
  title: string
  description: string
  priority: InsightPriority
  groupKey: string | null
  validated: boolean
  validationReasons: string[]
  createdAt: string
  updatedAt: string
}

export interface Recommendation {
  id: string
  sessionId: string
  insightIds: string[]
  evidenceIds: string[]
  title: string
  description: string
  rationale: string
  priority: RecommendationPriority
  status: RecommendationStatus
  impact: string
  effort: string
  createdAt: string
  updatedAt: string
}

export interface IntelligenceSummary {
  id: string
  sessionId: string
  planId: string
  title: string
  keyFindings: string[]
  insights: string[]
  recommendations: string[]
  conclusions: string[]
  createdAt: string
}

export interface IntelligenceActivity {
  id: string
  sessionId: string
  type: IntelligenceActivityType
  description: string
  metadata: Record<string, string>
  timestamp: string
}

export interface IntelligenceMetrics {
  workerId: string
  totalSessions: number
  activeSessions: number
  totalPlans: number
  totalObjectives: number
  totalEvidence: number
  totalInsights: number
  totalRecommendations: number
  totalSummaries: number
  totalActivities: number
  totalErrors: number
  averagePlanCompletionMs: number
  averageEvidencePerSession: number
  averageInsightsPerSession: number
  uptimeMs: number
  collectedAt: string
}

export interface IntelligencePolicy {
  id: string
  name: string
  description: string
  effect: IntelligencePolicyEffect
  category: string
  rules: IntelligencePolicyRule[]
  priority: number
  enabled: boolean
}

export interface IntelligencePolicyRule {
  field: string
  operator: "eq" | "neq" | "gt" | "gte" | "lt" | "lte" | "in" | "not_in" | "exists" | "not_exists"
  value: unknown
  message: string
}

export interface IntelligenceWorkerConfig {
  maxConcurrentSessions: number
  sessionTimeoutMs: number
  defaultRequestType: IntelligenceRequestType
  maxObjectivesPerPlan: number
  maxEvidencePerSession: number
  minEvidenceForInsight: number
  minInsightsForRecommendation: number
  policies: IntelligencePolicy[]
}

export type IntelligenceTaskPayload =
  | { type: "create_session"; request: IntelligenceRequest }
  | { type: "execute_plan"; sessionId: string; objectives: IntelligenceObjective[] }
  | { type: "process_evidence"; sessionId: string; evidenceItems: Omit<Evidence, "id" | "relationships" | "duplicateOf" | "createdAt">[] }
  | { type: "generate_insights"; sessionId: string; evidenceIds: string[] }
  | { type: "generate_recommendations"; sessionId: string; insightIds: string[]; evidenceIds: string[] }
  | { type: "build_summary"; sessionId: string }
  | { type: "control_session"; sessionId: string; action: "pause" | "resume" | "cancel" }
