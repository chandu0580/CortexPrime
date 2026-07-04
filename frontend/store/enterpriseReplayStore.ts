import { create } from "zustand"
import { enterpriseReplayService } from "@/services/enterpriseReplayService"
import type {
  MissionReplayData,
  WorkerReplayData,
  ConnectorReplayData,
  DecisionExplorerData,
  MemoryReplayData,
  KnowledgeGraphReplayData,
  CostReplayData,
  EventExplorerData,
  TimelineExplorerData,
  ExecutionGraphData,
} from "@/services/enterpriseReplayService"

export type ReplaySpeed = 0.25 | 0.5 | 1 | 2 | 4

export type EnterpriseReplayView =
  | "mission"
  | "workers"
  | "timeline"
  | "execution-graph"
  | "decisions"
  | "connectors"
  | "memory"
  | "knowledge-graph"
  | "costs"
  | "events"

interface EnterpriseReplayState {
  executionId: string | null

  mission: MissionReplayData | null
  workers: WorkerReplayData | null
  connectors: ConnectorReplayData | null
  decisions: DecisionExplorerData | null
  memory: MemoryReplayData | null
  knowledgeGraph: KnowledgeGraphReplayData | null
  costs: CostReplayData | null
  events: EventExplorerData | null
  timeline: TimelineExplorerData | null
  executionGraph: ExecutionGraphData | null

  activeView: EnterpriseReplayView
  currentSequence: number
  isPlaying: boolean
  playbackSpeed: ReplaySpeed

  isLoading: boolean
  error: string | null

  loadMission: (id: string) => Promise<void>
  loadWorkers: (id: string) => Promise<void>
  loadConnectors: (id: string) => Promise<void>
  loadDecisions: (id: string) => Promise<void>
  loadMemory: (id: string) => Promise<void>
  loadKnowledgeGraph: (id: string) => Promise<void>
  loadCosts: (id: string) => Promise<void>
  loadEvents: (id: string) => Promise<void>
  loadTimeline: (id: string, params?: { zoom?: string; agent?: string; event_type?: string }) => Promise<void>
  loadExecutionGraph: (id: string) => Promise<void>
  loadAll: (id: string) => Promise<void>

  setActiveView: (v: EnterpriseReplayView) => void
  play: () => void
  pause: () => void
  next: () => void
  previous: () => void
  seekTo: (index: number) => void
  setPlaybackSpeed: (speed: ReplaySpeed) => void
  reset: () => void
  _tick: () => void
}

const INITIAL = {
  executionId: null,
  mission: null,
  workers: null,
  connectors: null,
  decisions: null,
  memory: null,
  knowledgeGraph: null,
  costs: null,
  events: null,
  timeline: null,
  executionGraph: null,
  activeView: "mission" as EnterpriseReplayView,
  currentSequence: 0,
  isPlaying: false,
  playbackSpeed: 1 as ReplaySpeed,
  isLoading: false,
  error: null,
}

export const useEnterpriseReplayStore = create<EnterpriseReplayState>((set, get) => ({
  ...INITIAL,

  loadMission: async (id: string) => {
    set({ isLoading: true, error: null, executionId: id })
    try {
      const data = await enterpriseReplayService.getMissionReplay(id)
      set({ mission: data, isLoading: false })
    } catch (e: unknown) {
      set({ isLoading: false, error: e instanceof Error ? e.message : "Failed to load mission replay" })
    }
  },

  loadWorkers: async (id: string) => {
    try {
      const data = await enterpriseReplayService.getWorkerReplay(id)
      set({ workers: data })
    } catch { /* ignore */ }
  },

  loadConnectors: async (id: string) => {
    try {
      const data = await enterpriseReplayService.getConnectorReplay(id)
      set({ connectors: data })
    } catch { /* ignore */ }
  },

  loadDecisions: async (id: string) => {
    try {
      const data = await enterpriseReplayService.getDecisionExplorer(id)
      set({ decisions: data })
    } catch { /* ignore */ }
  },

  loadMemory: async (id: string) => {
    try {
      const data = await enterpriseReplayService.getMemoryReplay(id)
      set({ memory: data })
    } catch { /* ignore */ }
  },

  loadKnowledgeGraph: async (id: string) => {
    try {
      const data = await enterpriseReplayService.getKnowledgeGraphReplay(id)
      set({ knowledgeGraph: data })
    } catch { /* ignore */ }
  },

  loadCosts: async (id: string) => {
    try {
      const data = await enterpriseReplayService.getCostReplay(id)
      set({ costs: data })
    } catch { /* ignore */ }
  },

  loadEvents: async (id: string) => {
    try {
      const data = await enterpriseReplayService.getEventExplorer(id)
      set({ events: data })
    } catch { /* ignore */ }
  },

  loadTimeline: async (id: string, params?: { zoom?: string; agent?: string; event_type?: string }) => {
    try {
      const data = await enterpriseReplayService.getTimelineExplorer(id, params)
      set({ timeline: data })
    } catch { /* ignore */ }
  },

  loadExecutionGraph: async (id: string) => {
    try {
      const data = await enterpriseReplayService.getExecutionGraph(id)
      set({ executionGraph: data })
    } catch { /* ignore */ }
  },

  loadAll: async (id: string) => {
    set({ isLoading: true, error: null, executionId: id })
    try {
      const [mission, workers, connectors, decisions, memory, kg, costs, events, timeline, graph] =
        await Promise.all([
          enterpriseReplayService.getMissionReplay(id),
          enterpriseReplayService.getWorkerReplay(id),
          enterpriseReplayService.getConnectorReplay(id),
          enterpriseReplayService.getDecisionExplorer(id),
          enterpriseReplayService.getMemoryReplay(id),
          enterpriseReplayService.getKnowledgeGraphReplay(id),
          enterpriseReplayService.getCostReplay(id),
          enterpriseReplayService.getEventExplorer(id),
          enterpriseReplayService.getTimelineExplorer(id),
          enterpriseReplayService.getExecutionGraph(id),
        ])
      set({
        mission, workers, connectors, decisions, memory,
        knowledgeGraph: kg, costs, events, timeline, executionGraph: graph,
        isLoading: false,
      })
    } catch (e: unknown) {
      set({ isLoading: false, error: e instanceof Error ? e.message : "Failed to load enterprise replay data" })
    }
  },

  setActiveView: (v) => set({ activeView: v }),

  play: () => {
    const { timeline } = get()
    if (!timeline?.events.length) return
    set({ isPlaying: true })
  },

  pause: () => set({ isPlaying: false }),

  next: () => {
    const { timeline } = get()
    if (!timeline?.events.length) return
    const next = Math.min(get().currentSequence + 1, timeline.events.length - 1)
    set({ currentSequence: next })
  },

  previous: () => {
    const prev = Math.max(get().currentSequence - 1, 0)
    set({ currentSequence: prev })
  },

  seekTo: (index: number) => {
    const { timeline } = get()
    if (!timeline?.events.length) return
    set({ currentSequence: Math.max(0, Math.min(index, timeline.events.length - 1)) })
  },

  setPlaybackSpeed: (speed) => set({ playbackSpeed: speed }),

  reset: () => set({ ...INITIAL }),

  _tick: () => {
    const { isPlaying, currentSequence, timeline } = get()
    if (!isPlaying || !timeline) return
    const next = currentSequence + 1
    if (next >= timeline.events.length) {
      set({ isPlaying: false })
    } else {
      set({ currentSequence: next })
    }
  },
}))