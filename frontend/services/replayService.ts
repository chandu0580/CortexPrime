import axios from "axios";

import { apiUrl } from "@/lib/constants";

export interface ReplayEvent {
  event_id: string | null;
  execution_id: string;
  sequence: number;
  event_type: string;
  original_type: string | null;
  agent: string;
  status: string;
  message: string;
  timestamp: string | null;
  offset_ms: number | null;
  latency_ms: number | null;
  phase: string | null;
  confidence_score: number | null;
  token_usage: Record<string, number> | null;
  payload: Record<string, unknown>;
}

export interface ReplaySummary {
  execution_id: string;
  found: boolean;
  total_events: number | null;
  event_counts: Record<string, number> | null;
  agents: string[] | null;
  first_ts: string | null;
  last_ts: string | null;
  duration_ms: number | null;
  avg_latency_ms: number | null;
  is_complete: boolean | null;
}

export interface ReplayFull {
  summary: ReplaySummary;
  events: ReplayEvent[];
}

export interface GraphStep {
  sequence: number;
  event_type: string;
  agent: string;
  message: string;
  timestamp: string | null;
  agent_states: Record<string, string>;
}

export interface ReplayGraph {
  execution_id: string;
  total_steps: number;
  steps: GraphStep[];
  final_states: Record<string, string>;
}

export interface TimelineResponse {
  execution_id: string;
  count: number;
  events: ReplayEvent[];
}

export interface ReplayListResponse {
  executions: string[];
  count: number;
}

export const replayService = {
  /**
   * Full replay data — summary + all timeline events.
   */
  getFull: async (executionId: string): Promise<ReplayFull> => {
    const res = await axios.get<ReplayFull>(
      apiUrl(`/api/mission-replay/${executionId}`),
      { withCredentials: true }
    );
    return res.data;
  },

  /**
   * Lightweight ordered timeline with offset_ms.
   */
  getTimeline: async (
    executionId: string,
    params?: { agent?: string; event_type?: string }
  ): Promise<TimelineResponse> => {
    const res = await axios.get<TimelineResponse>(
      apiUrl(`/api/mission-replay/${executionId}/timeline`),
      { withCredentials: true, params }
    );
    return res.data;
  },

  /**
   * Per-step agent-state graph for animation.
   */
  getGraph: async (executionId: string): Promise<ReplayGraph> => {
    const res = await axios.get<ReplayGraph>(
      apiUrl(`/api/mission-replay/${executionId}/graph`),
      { withCredentials: true }
    );
    return res.data;
  },

  /**
   * List recent replay executions.
   */
  list: async (limit = 20): Promise<ReplayListResponse> => {
    const res = await axios.get<ReplayListResponse>(
      apiUrl("/api/mission-replay/"),
      { withCredentials: true, params: { limit } }
    );
    return res.data;
  },
};
