import { create } from "zustand"

export interface AdaptiveRecovery {
  id: string
  missionId: string
  stepId: string
  failureType: string
  failureMessage: string
  attemptCount: number
  maxAttempts: number
  strategy: string
  status: "pending" | "recovering" | "recovered" | "failed"
  startedAt?: string
  resolvedAt?: string
}

interface AdaptiveExecutionState {
  missionId: string | null
  activeRecoveries: AdaptiveRecovery[]
  completedRecoveries: AdaptiveRecovery[]
  failedRecoveries: AdaptiveRecovery[]
  adaptiveMode: boolean
  healthScore: number
  isHealing: boolean

  setMission: (missionId: string) => void
  setAdaptiveMode: (enabled: boolean) => void
  setHealthScore: (score: number) => void
  addRecovery: (recovery: AdaptiveRecovery) => void
  updateRecovery: (id: string, patch: Partial<AdaptiveRecovery>) => void
  resolveRecovery: (id: string, success: boolean) => void
  setHealing: (healing: boolean) => void
  reset: () => void
}

function generateId() {
  return `rec_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

export const useAdaptiveExecutionStore = create<AdaptiveExecutionState>((set) => ({
  missionId: null,
  activeRecoveries: [],
  completedRecoveries: [],
  failedRecoveries: [],
  adaptiveMode: true,
  healthScore: 100,
  isHealing: false,

  setMission: (missionId) => set({ missionId }),

  setAdaptiveMode: (enabled) => set({ adaptiveMode: enabled }),

  setHealthScore: (score) => set({ healthScore: Math.max(0, Math.min(100, score)) }),

  addRecovery: (recovery) =>
    set((s) => ({
      activeRecoveries: [...s.activeRecoveries, recovery],
    })),

  updateRecovery: (id, patch) =>
    set((s) => ({
      activeRecoveries: s.activeRecoveries.map((r) =>
        r.id === id ? { ...r, ...patch } : r
      ),
    })),

  resolveRecovery: (id, success) =>
    set((s) => {
      const recovery = s.activeRecoveries.find((r) => r.id === id)
      if (!recovery) return {}
      const resolved = {
        ...recovery,
        status: success ? "recovered" as const : "failed" as const,
        resolvedAt: new Date().toISOString(),
      }
      return {
        activeRecoveries: s.activeRecoveries.filter((r) => r.id !== id),
        completedRecoveries: success
          ? [...s.completedRecoveries, resolved]
          : s.completedRecoveries,
        failedRecoveries: success
          ? s.failedRecoveries
          : [...s.failedRecoveries, resolved],
      }
    }),

  setHealing: (healing) => set({ isHealing: healing }),

  reset: () => set({
    missionId: null,
    activeRecoveries: [],
    completedRecoveries: [],
    failedRecoveries: [],
    adaptiveMode: true,
    healthScore: 100,
    isHealing: false,
  }),
}))
