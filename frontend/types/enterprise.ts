export type MissionStatus = "pending" | "running" | "paused" | "cancelled" | "completed" | "failed"
export type MissionLifecycleState =
  | "mission_received" | "mission_analyzed" | "mission_planned"
  | "knowledge_retrieved" | "learning_retrieved" | "governance_evaluated"
  | "execution_planned" | "execution_started" | "execution_completed"
  | "verification" | "knowledge_updated" | "learning_updated" | "mission_archived"
export type AgentStatus = "idle" | "assigned" | "running" | "completed" | "failed" | "escalated"
export type CollaborationMode = "sequential" | "parallel" | "dependency" | "voting"

export interface OrchestratorMission {
  mission_id: string
  goal: string
  current_state: MissionLifecycleState
  status: MissionStatus
  error: string
  failure_category: string
  context: Record<string, unknown>
  created_at: string
  started_at: string
  completed_at: string
  stage_results: Record<string, StageResult>
  metadata: Record<string, unknown>
}

export interface StageResult {
  success: boolean
  error: string
  duration: number
  runtime: string
}

export interface StageMetrics {
  runtime_invoked: string
  connector_invoked: string
  duration_seconds: number
  success: boolean
  artifacts_produced: number
  errors: string[]
  decision_rationale: string
}

export interface MissionSummary {
  mission_id: string
  goal: string
  current_state: MissionLifecycleState
  status: MissionStatus
  error: string
  failure_category: string
  context: Record<string, unknown>
  stages: Record<string, StageResult>
  stage_metrics: Record<string, StageMetrics>
  timeline: TimelineEvent[]
  artifacts: ArtifactEntry[]
  artifact_count: number
  event_count: number
  reasoning_trace?: ReasoningStep[]
}

export interface TimelineEvent {
  mission_id: string
  state: string
  event_type: string
  source: string
  message: string
  timestamp: string
  correlation_id: string
}

export interface ArtifactEntry {
  artifact_id: string
  name: string
  artifact_type: string
  source: string
  state: string
  created_at: string
}

export interface ReasoningStep {
  description: string
  decision: string
  confidence: number
  critical: boolean
}

export interface AgentInfo {
  agent_id: string
  agent_type: string
  status: AgentStatus
  capabilities: string[]
}

export interface AgentResult {
  task_id: string
  agent_id: string
  agent_type: string
  success: boolean
  error: string
  duration_seconds: number
  voting_results: Record<string, unknown> | null
  delegation_chain: string[]
  output_data?: Record<string, unknown>
}

export interface AgentRunResponse {
  mission_id: string
  goal: string
  mode: string
  task_count: number
  results: AgentResult[]
  summary: { total: number; successful: number; failed: number }
}

export interface RuntimeStatus {
  runtimes: Record<string, boolean>
}

export interface HealthStatus {
  status: string
  active_sessions: number
  registered_agents: number
  active_missions: number
  total_missions: number
}

export interface KnowledgeEntry {
  id: string
  title: string
  content: string
  source: string
  confidence: number
  created_at: string
  tags: string[]
}

export interface GovernanceDecision {
  request_id: string
  decision: string
  message: string
  denied: boolean
  timestamp: string
}

export interface ConnectorInfo {
  connector_type: string
  name: string
  status: string
  capabilities: string[]
}

export interface ChatMessage {
  id: string
  role: "user" | "assistant" | "system"
  content: string
  timestamp: string
  metadata?: Record<string, unknown>
}

export interface TopologyNode {
  id: string
  type: string
  label: string
  status: string
  metrics: Record<string, number>
}

export interface TopologyEdge {
  source: string
  target: string
  label: string
  status: string
}
