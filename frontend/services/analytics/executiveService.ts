import axios from "axios";

import { apiUrl } from "@/lib/constants";

// ── Types ─────────────────────────────────────────────────────────────────

export interface SubsystemStatus {
  name:   string;
  status: "online" | "degraded" | "offline";
  value:  string;
  detail: string;
}

export interface HealthItem {
  label:  string;
  status: "healthy" | "degraded" | "offline";
  score:  number;
  detail: string;
}

export interface AgentStatus {
  id:          string;
  status:      "active" | "idle" | "processing" | "error";
  last_action: string;
}

export interface MissionInfo {
  execution_id:  string | null;
  goal:          string | null;
  stage:         string;
  progress:      number;
  active_agent:  string | null;
  started_at:    string | null;
  elapsed_secs:  number;
  health:        string;
}

export interface AutonomyDimension {
  label:  string;
  score:  number;
  detail: string;
}

export interface SnapshotResponse {
  timestamp:        string;
  system_status:    "online" | "degraded" | "offline";
  active_missions:  number;
  active_voice:     number;
  active_agents:    number;
  total_memories:   number;
  safety_score:     number;
  llm_provider:     string;
  current_mission:  MissionInfo | null;
  agents:           AgentStatus[];
  subsystems:       SubsystemStatus[];
  health_matrix:    HealthItem[];
  autonomy:         AutonomyDimension[];
  autonomy_overall: number;
  ws_connected:     boolean;
  uptime_hours:     number;
}

export interface AnalyticsSeries {
  date:              string;
  missions:          number;
  agent_events:      number;
  memory_ops:        number;
  voice_sessions:    number;
  governance_events: number;
  tool_calls:        number;
}

export interface AnalyticsResponse {
  series: AnalyticsSeries[];
  totals: Record<string, number>;
}

// ── Service ───────────────────────────────────────────────────────────────

class ExecutiveService {
  private base = apiUrl("/api/executive");

  async snapshot(): Promise<SnapshotResponse> {
    const { data } = await axios.get<SnapshotResponse>(`${this.base}/snapshot`, {
      withCredentials: true,
    });
    return data;
  }

  async analytics(): Promise<AnalyticsResponse> {
    const { data } = await axios.get<AnalyticsResponse>(`${this.base}/analytics`, {
      withCredentials: true,
    });
    return data;
  }
}

export const executiveService = new ExecutiveService();
