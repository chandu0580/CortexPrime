import axios from "axios"
import { apiUrl } from "@/lib/constants"

export interface WorkerAction {
  action_id: string
  worker_type: "browser" | "voice" | "desktop"
  action_type: string
  action: string
  input: string | null
  output: string | null
  status: string
  timestamp: string | null
  offset_ms: number | null
  duration_ms: number | null
  error: string | null
  metadata: Record<string, unknown>
}

export interface WorkerReplayData {
  execution_id: string
  total_actions: number
  workers: Record<string, WorkerAction[]>
  summary: Record<string, unknown>
  runtime_state: Record<string, string>
}

export interface ConnectorCall {
  connector_type: string
  endpoint: string
  method: string
  request: Record<string, unknown> | null
  response: Record<string, unknown> | null
  status: string
  timestamp: string | null
  offset_ms: number | null
  latency_ms: number | null
  error: string | null
  retry_count: number
}

export interface ConnectorReplayData {
  execution_id: string
  total_calls: number
  connectors: Record<string, ConnectorCall[]>
  summary: Record<string, unknown>
}

export interface LLMRequest {
  request_id: string
  provider: string
  model: string
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  prompt: string | null
  response: string | null
  timestamp: string | null
  offset_ms: number | null
  latency_ms: number | null
  confidence_score: number | null
  cost: number | null
}

export interface Decision {
  decision_id: string
  step: string
  agent: string
  reasoning: string | null
  llm_requests: LLMRequest[]
  confidence_score: number | null
  validation_result: string | null
  governance_action: string | null
  timestamp: string | null
  offset_ms: number | null
}

export interface DecisionExplorerData {
  execution_id: string
  total_decisions: number
  chain: Decision[]
  summary: Record<string, unknown>
}

export interface MemoryReplayEntry {
  memory_id: string
  memory_type: "working" | "semantic" | "episodic"
  content: string
  agent: string
  operation: string
  timestamp: string | null
  offset_ms: number | null
  relevance_score: number | null
  metadata: Record<string, unknown>
}

export interface MemoryReplayData {
  execution_id: string
  total_entries: number
  working_memory: MemoryReplayEntry[]
  semantic_memory: MemoryReplayEntry[]
  episodic_memory: MemoryReplayEntry[]
  changes_over_time: Record<string, unknown>[]
  summary: Record<string, unknown>
}

export interface GraphEntity {
  entity_id: string
  entity_type: string
  entity_name: string
  operation: string
  properties: Record<string, unknown>
  timestamp: string | null
  offset_ms: number | null
}

export interface GraphRelationship {
  relationship_id: string
  source: string
  target: string
  relationship_type: string
  operation: string
  timestamp: string | null
  offset_ms: number | null
}

export interface KnowledgeGraphReplayData {
  execution_id: string
  total_entities: number
  total_relationships: number
  entities: GraphEntity[]
  relationships: GraphRelationship[]
  evolution: Record<string, unknown>[]
  summary: Record<string, unknown>
}

export interface CostEntry {
  cost_id: string
  category: string
  provider: string | null
  model: string | null
  tokens: number | null
  cost: number
  timestamp: string | null
  date: string | null
  metadata: Record<string, unknown>
}

export interface CostReplayData {
  execution_id: string
  total_cost: number
  entries: CostEntry[]
  by_category: Record<string, number>
  by_day: Record<string, number>
  summary: Record<string, unknown>
}

export interface TimelineEntry {
  sequence: number
  event_type: string
  agent: string
  message: string
  timestamp: string | null
  offset_ms: number | null
  category: string
  metadata: Record<string, unknown>
}

export interface TimelineExplorerData {
  execution_id: string
  total_events: number
  events: TimelineEntry[]
  zoom_levels: string[]
  summary: Record<string, unknown>
}

export interface ExecutionGraphNode {
  id: string
  type: string
  label: string
  status: string
  duration_ms: number | null
  metadata: Record<string, unknown>
}

export interface ExecutionGraphEdge {
  source: string
  target: string
  label: string
  type: string
}

export interface ExecutionGraphData {
  execution_id: string
  nodes: ExecutionGraphNode[]
  edges: ExecutionGraphEdge[]
  summary: Record<string, unknown>
}

export interface EventExplorerEntry {
  event_id: string
  category: string
  event_type: string
  source: string
  agent: string | null
  message: string | null
  data: Record<string, unknown>
  timestamp: string | null
  offset_ms: number | null
  channel: string | null
}

export interface EventExplorerData {
  execution_id: string
  total_events: number
  events: EventExplorerEntry[]
  by_category: Record<string, number>
  by_source: Record<string, number>
  summary: Record<string, unknown>
}

export interface MissionReplayData {
  execution_id: string
  found: boolean
  status: string
  stages: string[]
  stage_events: Record<string, unknown>[]
  events: Record<string, unknown>[]
  metrics: Record<string, unknown>
  cost: Record<string, unknown>
  outcome: Record<string, unknown>
}

export interface ExportData {
  execution_id: string
  export_format: string
  exported_at: string
  summary: Record<string, unknown>
  events: Record<string, unknown>[]
  total_events: number
}

export const enterpriseReplayService = {
  getMissionReplay: async (executionId: string): Promise<MissionReplayData> => {
    const res = await axios.get<MissionReplayData>(
      apiUrl(`/api/enterprise-replay/mission/${executionId}`),
      { withCredentials: true }
    )
    return res.data
  },

  getWorkerReplay: async (executionId: string): Promise<WorkerReplayData> => {
    const res = await axios.get<WorkerReplayData>(
      apiUrl(`/api/enterprise-replay/workers/${executionId}`),
      { withCredentials: true }
    )
    return res.data
  },

  getConnectorReplay: async (executionId: string): Promise<ConnectorReplayData> => {
    const res = await axios.get<ConnectorReplayData>(
      apiUrl(`/api/enterprise-replay/connectors/${executionId}`),
      { withCredentials: true }
    )
    return res.data
  },

  getDecisionExplorer: async (executionId: string): Promise<DecisionExplorerData> => {
    const res = await axios.get<DecisionExplorerData>(
      apiUrl(`/api/enterprise-replay/decisions/${executionId}`),
      { withCredentials: true }
    )
    return res.data
  },

  getMemoryReplay: async (executionId: string): Promise<MemoryReplayData> => {
    const res = await axios.get<MemoryReplayData>(
      apiUrl(`/api/enterprise-replay/memory/${executionId}`),
      { withCredentials: true }
    )
    return res.data
  },

  getKnowledgeGraphReplay: async (executionId: string): Promise<KnowledgeGraphReplayData> => {
    const res = await axios.get<KnowledgeGraphReplayData>(
      apiUrl(`/api/enterprise-replay/knowledge-graph/${executionId}`),
      { withCredentials: true }
    )
    return res.data
  },

  getCostReplay: async (executionId: string): Promise<CostReplayData> => {
    const res = await axios.get<CostReplayData>(
      apiUrl(`/api/enterprise-replay/costs/${executionId}`),
      { withCredentials: true }
    )
    return res.data
  },

  getEventExplorer: async (executionId: string): Promise<EventExplorerData> => {
    const res = await axios.get<EventExplorerData>(
      apiUrl(`/api/enterprise-replay/events/${executionId}`),
      { withCredentials: true }
    )
    return res.data
  },

  getTimelineExplorer: async (
    executionId: string,
    params?: { zoom?: string; agent?: string; event_type?: string }
  ): Promise<TimelineExplorerData> => {
    const res = await axios.get<TimelineExplorerData>(
      apiUrl(`/api/enterprise-replay/timeline/${executionId}`),
      { withCredentials: true, params }
    )
    return res.data
  },

  getExecutionGraph: async (executionId: string): Promise<ExecutionGraphData> => {
    const res = await axios.get<ExecutionGraphData>(
      apiUrl(`/api/enterprise-replay/execution-graph/${executionId}`),
      { withCredentials: true }
    )
    return res.data
  },

  exportReplay: async (
    executionId: string,
    format: "json" | "markdown" | "timeline" | "replay-package"
  ): Promise<ExportData | string> => {
    const res = await axios.get(
      apiUrl(`/api/enterprise-replay/export/${executionId}`),
      { withCredentials: true, params: { format }, responseType: format === "markdown" ? "text" : "json" }
    )
    return res.data
  },
}
