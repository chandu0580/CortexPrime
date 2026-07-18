export interface DeliveryBlueprint {
  delivery_id: string
  mission: string
  repository: string
  workspace: string
  patch: string
  build: string
  artifacts: DeliveryArtifact[]
  tests: Record<string, unknown>
  coverage: Record<string, unknown>
  security_report: Record<string, unknown>
  approvals: ApprovalEntry[]
  deployment: string
  verification: Record<string, unknown>
  rollback: Record<string, unknown>
  metrics: Record<string, unknown>
  replay: ReplayReference[]
  learning_references: LearningReference[]
  recommendation_references: RecommendationReference[]
}

export interface DeliveryArtifact {
  id: string
  name: string
  path: string
  size_bytes: number
  type: string
  metadata: Record<string, unknown>
  created_at: string
}

export interface ApprovalEntry {
  approver: string
  decision: string
  reason: string
  timestamp: string
}

export interface ReplayReference {
  execution_id: string
  total_events: number
  summary: Record<string, unknown>
}

export interface LearningReference {
  lesson_id: string
  content: string
}

export interface RecommendationReference {
  rec_id: string
  title: string
}

export interface TimelineEntry {
  stage: string
  status: string
  message: string
  timestamp: string
  metadata: Record<string, unknown>
}

export interface DeliveryItem {
  delivery_id: string
  status: string
  state: string
  current_stage: string
  current_stage_index: number
  stages_completed: string[]
  stages_failed: string[]
  blueprint: DeliveryBlueprint
  timeline: TimelineEntry[]
  created_at: string
  updated_at: string
  started_at: string
  completed_at: string
  paused_at: string
  resumed_at: string
  error: string
  rollback_record: Record<string, unknown>
}

export type DeliveryState =
  | "pending" | "queued" | "running" | "waiting_approval"
  | "paused" | "retrying" | "completed" | "failed"
  | "cancelled" | "rolled_back" | "resumed"

export const DELIVERY_STAGES = [
  "repository", "workspace", "patch", "build", "qa",
  "security", "approval", "pr", "deployment", "verification",
  "monitoring", "learning",
] as const

export type DeliveryStage = typeof DELIVERY_STAGES[number]
