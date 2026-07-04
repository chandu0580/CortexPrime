import { create } from "zustand";
import {
  memoryExplorerService,
  MemoryRecord,
  TimelineDay,
  GraphNode,
  GraphEdge,
  HeatmapCell,
  StatsResponse,
  MemoryType,
} from "@/services/memoryExplorerService";

// ── State shape ───────────────────────────────────────────────────────────

interface MemoryExplorerState {
  // Search
  searchQuery:       string;
  searchResults:     MemoryRecord[];
  isSearching:       boolean;
  searchError:       string | null;
  memoryTypeFilter:  string;          // "all" or comma list
  agentFilter:       string;
  minScore:          number;
  selectedRecord:    MemoryRecord | null;

  // Timeline
  timeline:          TimelineDay[];
  timelineTotal:     number;
  isTimelineLoading: boolean;
  timelineDays:      number;

  // Graph
  graphNodes:        GraphNode[];
  graphEdges:        GraphEdge[];
  isGraphLoading:    boolean;

  // Stats + heatmap
  stats:             StatsResponse | null;
  isStatsLoading:    boolean;

  // Active tab
  activeView:        "search" | "timeline" | "graph" | "heatmap";

  // Actions
  setSearchQuery:      (q: string) => void;
  setMemoryTypeFilter: (t: string) => void;
  setAgentFilter:      (a: string) => void;
  setMinScore:         (s: number) => void;
  setSelectedRecord:   (r: MemoryRecord | null) => void;
  setActiveView:       (v: "search" | "timeline" | "graph" | "heatmap") => void;
  setTimelineDays:     (d: number) => void;

  search:       () => Promise<void>;
  loadTimeline: () => Promise<void>;
  loadGraph:    () => Promise<void>;
  loadStats:    () => Promise<void>;
}

// ── Store ─────────────────────────────────────────────────────────────────

export const useMemoryExplorerStore = create<MemoryExplorerState>((set, get) => ({
  // Initial state
  searchQuery:       "",
  searchResults:     [],
  isSearching:       false,
  searchError:       null,
  memoryTypeFilter:  "all",
  agentFilter:       "",
  minScore:          0,
  selectedRecord:    null,

  timeline:          [],
  timelineTotal:     0,
  isTimelineLoading: false,
  timelineDays:      30,

  graphNodes:        [],
  graphEdges:        [],
  isGraphLoading:    false,

  stats:             null,
  isStatsLoading:    false,

  activeView:        "search",

  // ── Setters ─────────────────────────────────────────────────────────
  setSearchQuery:      (q)  => set({ searchQuery: q }),
  setMemoryTypeFilter: (t)  => set({ memoryTypeFilter: t }),
  setAgentFilter:      (a)  => set({ agentFilter: a }),
  setMinScore:         (s)  => set({ minScore: s }),
  setSelectedRecord:   (r)  => set({ selectedRecord: r }),
  setActiveView:       (v)  => set({ activeView: v }),
  setTimelineDays:     (d)  => set({ timelineDays: d }),

  // ── Search ───────────────────────────────────────────────────────────
  search: async () => {
    const { searchQuery, memoryTypeFilter, agentFilter, minScore } = get();
    if (!searchQuery.trim()) return;
    set({ isSearching: true, searchError: null });
    try {
      const res = await memoryExplorerService.search({
        q:            searchQuery,
        limit:        50,
        memory_types: memoryTypeFilter,
        min_score:    minScore,
        agent_filter: agentFilter || undefined,
      });
      set({ searchResults: res.results, isSearching: false });
    } catch (e: unknown) {
      set({
        isSearching: false,
        searchError: e instanceof Error ? e.message : "Search failed",
      });
    }
  },

  // ── Timeline ─────────────────────────────────────────────────────────
  loadTimeline: async () => {
    const { timelineDays } = get();
    set({ isTimelineLoading: true });
    try {
      const res = await memoryExplorerService.timeline({ days: timelineDays });
      set({ timeline: res.timeline, timelineTotal: res.total, isTimelineLoading: false });
    } catch {
      set({ isTimelineLoading: false });
    }
  },

  // ── Graph ─────────────────────────────────────────────────────────────
  loadGraph: async () => {
    set({ isGraphLoading: true });
    try {
      const res = await memoryExplorerService.graph(100);
      set({ graphNodes: res.nodes, graphEdges: res.edges, isGraphLoading: false });
    } catch {
      set({ isGraphLoading: false });
    }
  },

  // ── Stats ─────────────────────────────────────────────────────────────
  loadStats: async () => {
    set({ isStatsLoading: true });
    try {
      const res = await memoryExplorerService.stats();
      set({ stats: res, isStatsLoading: false });
    } catch {
      set({ isStatsLoading: false });
    }
  },
}));
