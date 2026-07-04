import axios from "axios";

import { apiUrl } from "@/lib/constants";

// ── Shared types ──────────────────────────────────────────────────────────

export type PipelineStatus = "idle" | "active" | "approved" | "warned" | "blocked";

export interface PipelineStage {
  id:      string;
  label:   string;
  status:  PipelineStatus;
  latency: number | null;
  count:   number;
  last_at: string | null;
}

export interface OverviewResponse {
  pipeline:         PipelineStage[];
  active_missions:  number;
  blocked_today:    number;
  approved_today:   number;
  guardrail_hits:   number;
  emergency_stop:   boolean;
  compliance_score: number;
}

export interface RiskBucket {
  label:     string;
  low:       number;
  medium:    number;
  high:      number;
  critical:  number;
  total:     number;
  timestamp: string;
}

export interface RiskSeries {
  date:     string;
  low:      number;
  medium:   number;
  high:     number;
  critical: number;
  total:    number;
}

export interface RiskResponse {
  today:      RiskBucket;
  seven_day:  RiskBucket;
  thirty_day: RiskBucket;
  series:     RiskSeries[];
}

export type EventDecision = "approved" | "blocked" | "warned";

export interface GovernanceEvent {
  id:           string;
  event_type:   string;
  agent:        string;
  action:       string;
  target:       string;
  risk_level:   string;
  decision:     EventDecision;
  reason:       string;
  timestamp:    string;
  risk_score:   number | null;
  execution_id: string | null;
}

export interface EventsResponse {
  total:             number;
  events:            GovernanceEvent[];
  guardrail_summary: Record<string, number>;
}

export interface ComplianceCategory {
  label:   string;
  score:   number;
  trend:   number;
  details: string[];
}

export interface ComplianceResponse {
  overall:    number;
  grade:      string;
  categories: ComplianceCategory[];
  updated_at: string;
}

export interface ReplayGovernanceEvent {
  sequence:     number;
  stage:        string;
  agent:        string;
  action:       string;
  decision:     EventDecision;
  risk_level:   string;
  reason:       string;
  offset_ms:    number;
  timestamp:    string;
  metadata:     Record<string, unknown>;
}

export interface GovernanceReplayResponse {
  execution_id: string;
  total_events: number;
  duration_ms:  number;
  events:       ReplayGovernanceEvent[];
  summary:      Record<string, unknown>;
}

// ── Service ───────────────────────────────────────────────────────────────

class GovernanceCenterService {
  private base = apiUrl("/api/governance-center");

  async overview(): Promise<OverviewResponse> {
    const { data } = await axios.get<OverviewResponse>(`${this.base}/overview`, {
      withCredentials: true,
    });
    return data;
  }

  async risk(window: "today" | "7d" | "30d" = "30d"): Promise<RiskResponse> {
    const { data } = await axios.get<RiskResponse>(`${this.base}/risk`, {
      withCredentials: true,
      params:  { window },
    });
    return data;
  }

  async events(params?: {
    limit?:       number;
    event_type?:  string;
    decision?:    string;
  }): Promise<EventsResponse> {
    const { data } = await axios.get<EventsResponse>(`${this.base}/events`, {
      withCredentials: true,
      params,
    });
    return data;
  }

  async compliance(): Promise<ComplianceResponse> {
    const { data } = await axios.get<ComplianceResponse>(`${this.base}/compliance`, {
      withCredentials: true,
    });
    return data;
  }

  async replay(executionId: string): Promise<GovernanceReplayResponse> {
    const { data } = await axios.get<GovernanceReplayResponse>(
      `${this.base}/replay/${encodeURIComponent(executionId)}`,
      { withCredentials: true }
    );
    return data;
  }
}

export const governanceCenterService = new GovernanceCenterService();
