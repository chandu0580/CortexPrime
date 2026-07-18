import { create } from "zustand"

export interface DecisionAlternative {
  description: string
  pros: string[]
  cons: string[]
}

export interface DecisionRecord {
  id: string
  missionId: string
  decision: string
  rationale: string
  alternatives: DecisionAlternative[]
  outcome: "success" | "failure" | "partial" | "pending"
  confidence: number
  riskLevel: string
  timestamp: string
  metrics?: Record<string, number>
  tags?: string[]
}

interface DecisionMemoryState {
  decisions: DecisionRecord[]
  activeDecisionId: string | null
  isLoading: boolean
  error: string | null
  filter: {
    outcome?: string
    riskLevel?: string
    search?: string
  }

  setDecisions: (decisions: DecisionRecord[]) => void
  addDecision: (decision: DecisionRecord) => void
  updateDecision: (id: string, patch: Partial<DecisionRecord>) => void
  setActiveDecision: (id: string | null) => void
  setFilter: (filter: Partial<DecisionMemoryState["filter"]>) => void
  clearFilter: () => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  reset: () => void
}

export const useDecisionMemoryStore = create<DecisionMemoryState>((set) => ({
  decisions: [],
  activeDecisionId: null,
  isLoading: false,
  error: null,
  filter: {},

  setDecisions: (decisions) => set({ decisions, isLoading: false }),

  addDecision: (decision) =>
    set((s) => ({
      decisions: [decision, ...s.decisions],
    })),

  updateDecision: (id, patch) =>
    set((s) => ({
      decisions: s.decisions.map((d) =>
        d.id === id ? { ...d, ...patch } : d
      ),
    })),

  setActiveDecision: (id) => set({ activeDecisionId: id }),

  setFilter: (filter) =>
    set((s) => ({
      filter: { ...s.filter, ...filter },
    })),

  clearFilter: () => set({ filter: {} }),

  setLoading: (loading) => set({ isLoading: loading }),

  setError: (error) => set({ error }),

  reset: () => set({
    decisions: [],
    activeDecisionId: null,
    isLoading: false,
    error: null,
    filter: {},
  }),
}))
