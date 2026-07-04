// ==========================================
// MISSION CONTROL — Domain Models
// These are frontend-only normalized types.
// They are NOT backend API response shapes.
// ==========================================

// ─── Identifiers ───────────────────────────────

export type MissionId = string

// ─── Lifecycle ─────────────────────────────────

export type MissionStatus =
  | "draft"
  | "queued"
  | "validating"
  | "planning"
  | "ready"
  | "executing"
  | "paused"
  | "completed"
  | "failed"
  | "cancelled"

export type MissionPriority = "low" | "medium" | "high" | "critical"

export type MissionStage =
  | "intake"
  | "analysis"
  | "planning"
  | "decomposition"
  | "assignment"
  | "execution"
  | "review"
  | "completion"

// ─── Core Mission ──────────────────────────────

export interface Mission {
  id: MissionId
  title: string
  description: string
  status: MissionStatus
  priority: MissionPriority
  stage: MissionStage
  createdAt: Date
  updatedAt: Date
  startedAt: Date | null
  completedAt: Date | null
  tags: string[]
  owner: string
  progress: number
  agents: MissionAgentAssignment[]
  parentId: MissionId | null
}

// ─── Summary (list view) ───────────────────────

export interface MissionSummary {
  id: MissionId
  title: string
  status: MissionStatus
  priority: MissionPriority
  stage: MissionStage
  progress: number
  agentCount: number
  createdAt: Date
  completedAt: Date | null
}

// ─── Agent Assignment ──────────────────────────

export interface MissionAgentAssignment {
  agentId: string
  agentName: string
  role: string
  status: "idle" | "working" | "completed" | "failed"
  startedAt: Date | null
  completedAt: Date | null
}

// ─── Execution ─────────────────────────────────

export interface MissionExecution {
  missionId: MissionId
  status: MissionStatus
  currentStage: MissionStage
  progress: number
  startedAt: Date | null
  activeAgents: MissionAgentAssignment[]
  currentStep: string
  state: "running" | "paused" | "stopped"
}

// ─── Timeline ──────────────────────────────────

export interface MissionTimelineEntry {
  id: string
  missionId: MissionId
  type: "stage_change" | "status_change" | "agent_action" | "system_event" | "user_intervention"
  timestamp: Date
  description: string
  actor: string
  metadata?: Record<string, unknown>
}

// ─── Activity Feed ─────────────────────────────

export interface MissionActivity {
  id: string
  missionId: MissionId
  severity: "info" | "success" | "warning" | "error"
  message: string
  timestamp: Date
  agentId?: string
}

// ─── Actions ────────────────────────────────────

export interface MissionAction {
  id: string
  label: string
  action: string
  enabled: boolean
  requiresConfirmation: boolean
}

// ─── Artifacts ──────────────────────────────────

export interface MissionArtifact {
  id: string
  missionId: MissionId
  type: "report" | "dataset" | "code" | "document" | "insight" | "decision"
  title: string
  description: string
  createdAt: Date
  format: string
}

// ─── Result ─────────────────────────────────────

export interface MissionResult {
  missionId: MissionId
  summary: string
  artifacts: MissionArtifact[]
  metrics: MissionMetrics
  completedAt: Date
  durationMs: number
}

// ─── Metrics ────────────────────────────────────

export interface MissionMetrics {
  totalSteps: number
  completedSteps: number
  failedSteps: number
  totalAgents: number
  durationMs: number
  tokenCount: number
  estimatedCost: number
  successRate: number
}
