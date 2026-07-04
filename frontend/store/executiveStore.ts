import { create } from "zustand";
import {
  executiveService,
  type SnapshotResponse,
  type AnalyticsResponse,
} from "@/services/executiveService";

interface ExecutiveState {
  snapshot:          SnapshotResponse | null;
  analytics:         AnalyticsResponse | null;
  isLoading:         boolean;
  isAnalyticsLoading: boolean;
  lastRefresh:       number;
  error:             string | null;

  loadSnapshot:  () => Promise<void>;
  loadAnalytics: () => Promise<void>;
  refreshAll:    () => Promise<void>;
}

export const useExecutiveStore = create<ExecutiveState>((set, get) => ({
  snapshot:           null,
  analytics:          null,
  isLoading:          false,
  isAnalyticsLoading: false,
  lastRefresh:        0,
  error:              null,

  loadSnapshot: async () => {
    set({ isLoading: true, error: null });
    try {
      const data = await executiveService.snapshot();
      set({ snapshot: data, isLoading: false, lastRefresh: Date.now() });
    } catch (e: unknown) {
      set({ isLoading: false, error: e instanceof Error ? e.message : "Load failed" });
    }
  },

  loadAnalytics: async () => {
    set({ isAnalyticsLoading: true });
    try {
      const data = await executiveService.analytics();
      set({ analytics: data, isAnalyticsLoading: false });
    } catch {
      set({ isAnalyticsLoading: false });
    }
  },

  refreshAll: async () => {
    await Promise.all([get().loadSnapshot(), get().loadAnalytics()]);
  },
}));
