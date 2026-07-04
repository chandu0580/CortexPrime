import { create } from "zustand";
import { replayService, ReplayEvent, ReplaySummary, GraphStep } from "@/services/replayService";

export type PlaybackSpeed = 0.25 | 0.5 | 1 | 2 | 4;

interface ReplayState {
  // Data
  executionId: string | null;
  summary: ReplaySummary | null;
  events: ReplayEvent[];
  graphSteps: GraphStep[];

  // Playback
  currentSequence: number;       // 0-based index into events[]
  totalSequences: number;
  isPlaying: boolean;
  playbackSpeed: PlaybackSpeed;

  // UI
  isLoading: boolean;
  error: string | null;

  // Derived — current agent states for graph overlay
  currentAgentStates: Record<string, string>;

  // Actions
  loadReplay: (executionId: string) => Promise<void>;
  play: () => void;
  pause: () => void;
  next: () => void;
  previous: () => void;
  seekTo: (index: number) => void;
  setPlaybackSpeed: (speed: PlaybackSpeed) => void;
  reset: () => void;

  // Internal
  _tick: () => void;
}

const INITIAL_STATE: Omit<ReplayState, "loadReplay" | "play" | "pause" | "next" | "previous" | "seekTo" | "setPlaybackSpeed" | "reset" | "_tick"> = {
  executionId: null,
  summary: null,
  events: [],
  graphSteps: [],
  currentSequence: 0,
  totalSequences: 0,
  isPlaying: false,
  playbackSpeed: 1,
  isLoading: false,
  error: null,
  currentAgentStates: {},
};

function buildAgentStates(
  graphSteps: GraphStep[],
  index: number
): Record<string, string> {
  if (!graphSteps.length || index < 0) return {};
  const step = graphSteps[Math.min(index, graphSteps.length - 1)];
  return step?.agent_states ?? {};
}

export const useReplayStore = create<ReplayState>((set, get) => ({
  ...INITIAL_STATE,

  // ----------------------------------------------------------------
  // loadReplay — fetch all replay data for an execution
  // ----------------------------------------------------------------
  loadReplay: async (executionId: string) => {
    set({ isLoading: true, error: null, executionId });

    try {
      const [full, graph] = await Promise.all([
        replayService.getFull(executionId),
        replayService.getGraph(executionId),
      ]);

      set({
        summary: full.summary,
        events: full.events,
        graphSteps: graph.steps,
        totalSequences: full.events.length,
        currentSequence: 0,
        currentAgentStates: buildAgentStates(graph.steps, 0),
        isPlaying: false,
        isLoading: false,
        error: null,
      });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to load replay";
      set({ isLoading: false, error: message });
    }
  },

  // ----------------------------------------------------------------
  // Playback controls
  // ----------------------------------------------------------------
  play: () => {
    const { totalSequences, currentSequence } = get();
    if (totalSequences === 0) return;
    // If at end, restart from beginning
    const startFrom = currentSequence >= totalSequences - 1 ? 0 : currentSequence;
    set({ isPlaying: true, currentSequence: startFrom });
  },

  pause: () => set({ isPlaying: false }),

  next: () => {
    const { currentSequence, totalSequences, graphSteps } = get();
    const next = Math.min(currentSequence + 1, totalSequences - 1);
    set({
      currentSequence: next,
      currentAgentStates: buildAgentStates(graphSteps, next),
    });
  },

  previous: () => {
    const { currentSequence, graphSteps } = get();
    const prev = Math.max(currentSequence - 1, 0);
    set({
      currentSequence: prev,
      currentAgentStates: buildAgentStates(graphSteps, prev),
    });
  },

  seekTo: (index: number) => {
    const { totalSequences, graphSteps } = get();
    const clamped = Math.max(0, Math.min(index, totalSequences - 1));
    set({
      currentSequence: clamped,
      currentAgentStates: buildAgentStates(graphSteps, clamped),
    });
  },

  setPlaybackSpeed: (speed: PlaybackSpeed) => set({ playbackSpeed: speed }),

  reset: () =>
    set({
      ...INITIAL_STATE,
    }),

  // ----------------------------------------------------------------
  // _tick — advance one frame; called from a timer in components
  // ----------------------------------------------------------------
  _tick: () => {
    const { isPlaying, currentSequence, totalSequences, graphSteps } = get();
    if (!isPlaying) return;
    const next = currentSequence + 1;
    if (next >= totalSequences) {
      // Reached end — stop
      set({ isPlaying: false });
    } else {
      set({
        currentSequence: next,
        currentAgentStates: buildAgentStates(graphSteps, next),
      });
    }
  },
}));
