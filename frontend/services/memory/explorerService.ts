import axios from "axios";

import { apiUrl } from "@/lib/constants";

// ── Types ─────────────────────────────────────────────────────────────────

export type MemoryType =
  | "episodic"
  | "semantic"
  | "reflection"
  | "workspace"
  | "voice"
  | "browser";

export interface MemoryRecord {
  id: string;
  memory_type: MemoryType;
  content: string;
  agent: string | null;
  concept: string | null;
  event_type: string | null;
  session_id: string | null;
  mission_id: string | null;
  source: string | null;
  similarity_score: number | null;
  confidence: number | null;
  retrieval_count: number;
  created_at: string;
  last_retrieved: string | null;
  metadata: Record<string, unknown>;
}

export interface SearchResponse {
  query: string;
  count: number;
  results: MemoryRecord[];
}

export interface TimelineDay {
  date: string;        // YYYY-MM-DD
  count: number;
  records: MemoryRecord[];
}

export interface TimelineResponse {
  days: number;
  total: number;
  day_count: number;
  timeline: TimelineDay[];
}

export interface GraphNode {
  id: string;
  label: string;
  memory_type: MemoryType;
  agent: string | null;
  weight: number;
  created_at: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  relation: string;
  weight: number;
}

export interface GraphResponse {
  node_count: number;
  edge_count: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface HeatmapCell {
  id: string;
  label: string;
  memory_type: MemoryType;
  retrieval_count: number;
  created_at: string;
  agent: string | null;
}

export interface StatsResponse {
  total: number;
  by_type: Record<string, number>;
  by_agent: Record<string, number>;
  avg_similarity: number | null;
  heatmap: HeatmapCell[];
  date_distribution: Record<string, number>;
}

// ── Service ───────────────────────────────────────────────────────────────

export const memoryExplorerService = {
  /**
   * Cross-store similarity / text search.
   */
  search: async (params: {
    q: string;
    limit?: number;
    memory_types?: string;
    min_score?: number;
    agent_filter?: string;
  }): Promise<SearchResponse> => {
    const res = await axios.get<SearchResponse>(
      apiUrl("/api/memory/explorer/search"),
      { withCredentials: true, params }
    );
    return res.data;
  },

  /**
   * Timeline grouped by date.
   */
  timeline: async (params?: {
    days?: number;
    limit_per_day?: number;
  }): Promise<TimelineResponse> => {
    const res = await axios.get<TimelineResponse>(
      apiUrl("/api/memory/explorer/timeline"),
      { withCredentials: true, params }
    );
    return res.data;
  },

  /**
   * Node-edge graph data.
   */
  graph: async (limit?: number): Promise<GraphResponse> => {
    const res = await axios.get<GraphResponse>(
      apiUrl("/api/memory/explorer/graph"),
      { withCredentials: true, params: { limit } }
    );
    return res.data;
  },

  /**
   * Aggregate stats + heatmap.
   */
  stats: async (): Promise<StatsResponse> => {
    const res = await axios.get<StatsResponse>(
      apiUrl("/api/memory/explorer/stats"),
      { withCredentials: true }
    );
    return res.data;
  },
};
