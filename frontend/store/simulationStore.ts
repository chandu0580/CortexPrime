import { create } from "zustand"

export interface SimulationMetric {
  label: string
  value: string | number
}

export interface SimulationRisk {
  description: string
  severity: "low" | "medium" | "high"
}

export interface SimulationScenario {
  id: string
  name: string
  description: string
  predictedOutcome: "success" | "failure" | "degraded"
  confidence: number
  metrics: SimulationMetric[]
  risks: SimulationRisk[]
  recommendation: string
}

export type SimulationType = "execution" | "path" | "failure" | "approval" | "rollback"

export interface SimulationResult {
  id: string
  missionId: string
  type: SimulationType
  status: "pending" | "running" | "completed" | "failed"
  scenarios: SimulationScenario[]
  startedAt?: string
  completedAt?: string
  error?: string
}

interface SimulationState {
  simulations: SimulationResult[]
  activeSimulationId: string | null
  isSimulating: boolean
  error: string | null

  startSimulation: (missionId: string, type: SimulationType) => void
  addScenario: (scenario: SimulationScenario) => void
  completeSimulation: () => void
  failSimulation: (error: string) => void
  setActiveSimulation: (id: string | null) => void
  clearSimulations: () => void
}

function generateId() {
  return `sim_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

export const useSimulationStore = create<SimulationState>((set) => ({
  simulations: [],
  activeSimulationId: null,
  isSimulating: false,
  error: null,

  startSimulation: (missionId, type) => {
    const sim: SimulationResult = {
      id: generateId(),
      missionId,
      type,
      status: "running",
      scenarios: [],
      startedAt: new Date().toISOString(),
    }
    set((s) => ({
      simulations: [sim, ...s.simulations],
      activeSimulationId: sim.id,
      isSimulating: true,
      error: null,
    }))
  },

  addScenario: (scenario) => set((s) => {
    if (!s.activeSimulationId) return {}
    return {
      simulations: s.simulations.map((sim) =>
        sim.id === s.activeSimulationId
          ? { ...sim, scenarios: [...sim.scenarios, scenario] }
          : sim
      ),
    }
  }),

  completeSimulation: () => set((s) => ({
    isSimulating: false,
    simulations: s.simulations.map((sim) =>
      sim.id === s.activeSimulationId
        ? { ...sim, status: "completed", completedAt: new Date().toISOString() }
        : sim
    ),
  })),

  failSimulation: (error) => set((s) => ({
    isSimulating: false,
    error,
    simulations: s.simulations.map((sim) =>
      sim.id === s.activeSimulationId
        ? { ...sim, status: "failed", completedAt: new Date().toISOString(), error }
        : sim
    ),
  })),

  setActiveSimulation: (id) => set({ activeSimulationId: id }),

  clearSimulations: () => set({ simulations: [], activeSimulationId: null, error: null }),
}))
