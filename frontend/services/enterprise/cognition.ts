import axios from "axios"
import { apiUrl } from "@/lib/constants"

export interface CognitionStatus {
  state: string
  current_phase: string
  loop_count: number
  started_at: string
  last_repo_check: string
  last_infra_check: string
  known_repositories_count: number
  known_services_count: number
  timeline_entries_count: number
  loop_interval_seconds: number
  repo_interval_seconds: number
  infra_interval_seconds: number
}

export interface TimelineEntry {
  entry_id: string
  timestamp: string
  phase: string
  change_type: string
  reason: string
  affected_repositories: string[]
  affected_services: string[]
  previous_state: Record<string, unknown> | null
  new_state: Record<string, unknown> | null
  confidence: number
  triggered_actions: string[]
  risk_before: number | null
  risk_after: number | null
  prediction_id: string | null
  mission_id: string | null
}

export interface Observation {
  type: string
  reason: string
  timestamp: string
  confidence: number
  repositories: string[]
  services: string[]
  risk_before: number | null
  risk_after: number | null
}

export interface RiskEvolution {
  repository: string
  score: number
}

export interface ArchitectureChange {
  type: string
  repository: string
  timestamp: string
  reason: string
}

export interface CognitionDashboard {
  status: CognitionStatus
  latest_observations: Observation[]
  risk_evolution: RiskEvolution[]
  architecture_changes: ArchitectureChange[]
  timeline: TimelineEntry[]
  repository_brain: Record<string, unknown>
  infra_health_baseline: Record<string, unknown>
}

export interface CognitionHealth {
  status: string
  cognition_runtime: string
  available_sources: number
  total_sources: number
  sources: Record<string, boolean>
}

export interface IntervalConfig {
  loop_interval_seconds?: number
  repo_check_interval_seconds?: number
  infra_check_interval_seconds?: number
}

export const enterpriseCognitionApi = {
  getStatus: async (): Promise<CognitionStatus> => {
    const res = await axios.get(apiUrl("/api/cognition/status"))
    return res.data
  },

  getDashboard: async (): Promise<CognitionDashboard> => {
    const res = await axios.get(apiUrl("/api/cognition/dashboard"))
    return res.data
  },

  getTimeline: async (
    limit = 50,
    offset = 0,
    changeType?: string,
  ): Promise<TimelineEntry[]> => {
    const params: Record<string, string | number> = { limit, offset }
    if (changeType) params.change_type = changeType
    const res = await axios.get(apiUrl("/api/cognition/timeline"), { params })
    return res.data
  },

  start: async (config?: IntervalConfig): Promise<{ status: string }> => {
    const res = await axios.post(apiUrl("/api/cognition/start"), config ?? {})
    return res.data
  },

  stop: async (): Promise<{ status: string }> => {
    const res = await axios.post(apiUrl("/api/cognition/stop"))
    return res.data
  },

  pause: async (): Promise<{ status: string }> => {
    const res = await axios.post(apiUrl("/api/cognition/pause"))
    return res.data
  },

  resume: async (): Promise<{ status: string }> => {
    const res = await axios.post(apiUrl("/api/cognition/resume"))
    return res.data
  },

  getHealth: async (): Promise<CognitionHealth> => {
    const res = await axios.get(apiUrl("/api/cognition/health"))
    return res.data
  },
}
