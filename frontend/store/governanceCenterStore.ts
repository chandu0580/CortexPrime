import { create } from "zustand";
import {
  governanceCenterService,
  type OverviewResponse,
  type RiskResponse,
  type EventsResponse,
  type ComplianceResponse,
  type GovernanceReplayResponse,
} from "@/services/governanceCenterService";

export type GovernanceView = "pipeline" | "risk" | "events" | "guardrails" | "replay" | "compliance";

interface GovernanceCenterState {
  // Overview / pipeline
  overview:         OverviewResponse | null;
  isOverviewLoading: boolean;
  overviewError:    string | null;

  // Risk
  risk:             RiskResponse | null;
  isRiskLoading:    boolean;

  // Events
  events:           EventsResponse | null;
  isEventsLoading:  boolean;
  eventFilter:      string | null;   // null = all
  decisionFilter:   string | null;

  // Compliance
  compliance:       ComplianceResponse | null;
  isComplianceLoading: boolean;

  // Replay
  replayData:       GovernanceReplayResponse | null;
  replayExecId:     string;
  isReplayLoading:  boolean;
  replaySequence:   number;
  replayPlaying:    boolean;

  // UI
  activeView:       GovernanceView;
  lastRefresh:      number;

  // Actions
  setActiveView:     (v: GovernanceView) => void;
  setEventFilter:    (f: string | null) => void;
  setDecisionFilter: (f: string | null) => void;
  setReplayExecId:   (id: string) => void;
  setReplaySequence: (n: number) => void;
  setReplayPlaying:  (p: boolean) => void;

  loadOverview:    () => Promise<void>;
  loadRisk:        () => Promise<void>;
  loadEvents:      () => Promise<void>;
  loadCompliance:  () => Promise<void>;
  loadReplay:      (id: string) => Promise<void>;
  refreshAll:      () => Promise<void>;
}

export const useGovernanceCenterStore = create<GovernanceCenterState>((set, get) => ({
  overview:            null,
  isOverviewLoading:   false,
  overviewError:       null,
  risk:                null,
  isRiskLoading:       false,
  events:              null,
  isEventsLoading:     false,
  eventFilter:         null,
  decisionFilter:      null,
  compliance:          null,
  isComplianceLoading: false,
  replayData:          null,
  replayExecId:        "",
  isReplayLoading:     false,
  replaySequence:      0,
  replayPlaying:       false,
  activeView:          "pipeline",
  lastRefresh:         0,

  setActiveView:     (v) => set({ activeView: v }),
  setEventFilter:    (f) => set({ eventFilter: f }),
  setDecisionFilter: (f) => set({ decisionFilter: f }),
  setReplayExecId:   (id) => set({ replayExecId: id }),
  setReplaySequence: (n) => set({ replaySequence: n }),
  setReplayPlaying:  (p) => set({ replayPlaying: p }),

  loadOverview: async () => {
    set({ isOverviewLoading: true, overviewError: null });
    try {
      const data = await governanceCenterService.overview();
      set({ overview: data, isOverviewLoading: false, lastRefresh: Date.now() });
    } catch (e: unknown) {
      set({
        isOverviewLoading: false,
        overviewError: e instanceof Error ? e.message : "Failed to load overview",
      });
    }
  },

  loadRisk: async () => {
    set({ isRiskLoading: true });
    try {
      const data = await governanceCenterService.risk("30d");
      set({ risk: data, isRiskLoading: false });
    } catch {
      set({ isRiskLoading: false });
    }
  },

  loadEvents: async () => {
    set({ isEventsLoading: true });
    try {
      const { eventFilter, decisionFilter } = get();
      const data = await governanceCenterService.events({
        limit:       100,
        event_type:  eventFilter ?? undefined,
        decision:    decisionFilter ?? undefined,
      });
      set({ events: data, isEventsLoading: false });
    } catch {
      set({ isEventsLoading: false });
    }
  },

  loadCompliance: async () => {
    set({ isComplianceLoading: true });
    try {
      const data = await governanceCenterService.compliance();
      set({ compliance: data, isComplianceLoading: false });
    } catch {
      set({ isComplianceLoading: false });
    }
  },

  loadReplay: async (id: string) => {
    if (!id) return;
    set({ isReplayLoading: true, replaySequence: 0, replayPlaying: false });
    try {
      const data = await governanceCenterService.replay(id);
      set({ replayData: data, isReplayLoading: false, replayExecId: id });
    } catch {
      set({ isReplayLoading: false });
    }
  },

  refreshAll: async () => {
    const { loadOverview, loadRisk, loadEvents, loadCompliance } = get();
    await Promise.all([loadOverview(), loadRisk(), loadEvents(), loadCompliance()]);
  },
}));
