import { create } from "zustand"
import { executiveIntelligence, type IntelligenceSnapshot } from "@/services/intelligence/executiveIntelligence"

interface IntelligenceState {
  snapshot: IntelligenceSnapshot | null
  isLoading: boolean
  commandPaletteOpen: boolean
  globalSearchOpen: boolean
  lastRefresh: string | null
  error: string | null

  loadSnapshot: () => Promise<void>
  refreshAll: () => Promise<void>
  setCommandPalette: (open: boolean) => void
  setGlobalSearch: (open: boolean) => void
}

export const useIntelligenceStore = create<IntelligenceState>((set, get) => ({
  snapshot: null,
  isLoading: false,
  commandPaletteOpen: false,
  globalSearchOpen: false,
  lastRefresh: null,
  error: null,

  loadSnapshot: async () => {
    set({ isLoading: true, error: null })
    try {
      const snapshot = await executiveIntelligence.getSnapshot()
      set({ snapshot, isLoading: false, lastRefresh: new Date().toISOString() })
    } catch (err) {
      set({ isLoading: false, error: err instanceof Error ? err.message : "Failed to load intelligence" })
    }
  },

  refreshAll: async () => {
    executiveIntelligence.clearCache()
    await get().loadSnapshot()
  },

  setCommandPalette: (open) => set({ commandPaletteOpen: open }),
  setGlobalSearch: (open) => set({ globalSearchOpen: open }),
}))