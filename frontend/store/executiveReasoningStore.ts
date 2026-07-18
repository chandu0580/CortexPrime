import { create } from "zustand"

export interface ReasoningStep {
  id: string
  type: "goal_analysis" | "context_evaluation" | "constraint_identification" | "dependency_mapping" | "assumption_check" | "outcome_projection" | "strategy_formulation" | "confidence_assessment" | "risk_evaluation" | "recommendation"
  title: string
  description: string
  status: "pending" | "in_progress" | "completed" | "failed"
  confidence?: number
  details?: Record<string, unknown>
  startedAt?: string
  completedAt?: string
}

export interface StrategyOption {
  name: string
  description: string
  confidence: number
  risk: "low" | "medium" | "high"
}

export interface ReasoningSession {
  id: string
  missionId: string
  goal: string
  context: string
  constraints: string[]
  dependencies: string[]
  assumptions: string[]
  expectedOutcome: string
  strategies: StrategyOption[]
  overallConfidence: number
  riskLevel: "low" | "medium" | "high" | "critical"
  recommendation: string
  steps: ReasoningStep[]
  status: "idle" | "reasoning" | "completed" | "failed"
  startedAt?: string
  completedAt?: string
}

interface ExecutiveReasoningState {
  sessions: ReasoningSession[]
  activeSessionId: string | null
  isReasoning: boolean
  error: string | null

  startReasoning: (goal: string, context?: string) => void
  addStep: (step: ReasoningStep) => void
  updateStep: (stepId: string, patch: Partial<ReasoningStep>) => void
  completeStep: (stepId: string) => void
  setActiveSession: (sessionId: string | null) => void
  completeReasoning: () => void
  failReasoning: (error: string) => void
  reset: () => void
}

function generateId() {
  return `reason_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

export const useExecutiveReasoningStore = create<ExecutiveReasoningState>((set) => ({
  sessions: [],
  activeSessionId: null,
  isReasoning: false,
  error: null,

  startReasoning: (goal, context = "") => {
    const session: ReasoningSession = {
      id: generateId(),
      missionId: "",
      goal,
      context,
      constraints: [],
      dependencies: [],
      assumptions: [],
      expectedOutcome: "",
      strategies: [],
      overallConfidence: 0,
      riskLevel: "medium",
      recommendation: "",
      steps: [],
      status: "reasoning",
      startedAt: new Date().toISOString(),
    }
    const current = useExecutiveReasoningStore.getState().sessions
    set({ sessions: [session, ...current], activeSessionId: session.id, isReasoning: true, error: null })
  },

  addStep: (step) => set((s) => {
    const active = s.sessions.find((ses) => ses.id === s.activeSessionId)
    if (!active) return {}
    return {
      sessions: s.sessions.map((ses) =>
        ses.id === s.activeSessionId
          ? { ...ses, steps: [...ses.steps, step] }
          : ses
      ),
    }
  }),

  updateStep: (stepId, patch) => set((s) => ({
    sessions: s.sessions.map((ses) =>
      ses.id === s.activeSessionId
        ? {
            ...ses,
            steps: ses.steps.map((st) =>
              st.id === stepId ? { ...st, ...patch } : st
            ),
          }
        : ses
    ),
  })),

  completeStep: (stepId) => set((s) => ({
    sessions: s.sessions.map((ses) =>
      ses.id === s.activeSessionId
        ? {
            ...ses,
            steps: ses.steps.map((st) =>
              st.id === stepId
                ? { ...st, status: "completed", completedAt: new Date().toISOString() }
                : st
            ),
          }
        : ses
    ),
  })),

  setActiveSession: (sessionId) => set({ activeSessionId: sessionId }),

  completeReasoning: () => set((s) => ({
    isReasoning: false,
    sessions: s.sessions.map((ses) =>
      ses.id === s.activeSessionId
        ? { ...ses, status: "completed", completedAt: new Date().toISOString() }
        : ses
    ),
  })),

  failReasoning: (error) => set((s) => ({
    isReasoning: false,
    error,
    sessions: s.sessions.map((ses) =>
      ses.id === s.activeSessionId
        ? { ...ses, status: "failed", completedAt: new Date().toISOString() }
        : ses
    ),
  })),

  reset: () => set({ sessions: [], activeSessionId: null, isReasoning: false, error: null }),
}))
