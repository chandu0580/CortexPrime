import { create } from "zustand"

export interface ObservationMetric {
  label: string
  value: string | number
  status: "healthy" | "warning" | "critical"
  trend: "up" | "down" | "stable"
  timestamp: string
}

export interface ObservationAlert {
  id: string
  severity: "info" | "warning" | "critical"
  source: string
  message: string
  timestamp: string
  acknowledged: boolean
}

export interface ObservationCategory {
  id: string
  label: string
  metrics: ObservationMetric[]
  alerts: ObservationAlert[]
}

interface ObservationState {
  categories: ObservationCategory[]
  metrics: ObservationMetric[]
  alerts: ObservationAlert[]
  isObserving: boolean
  lastUpdate: string | null

  setCategories: (categories: ObservationCategory[]) => void
  updateCategory: (id: string, patch: Partial<ObservationCategory>) => void
  setMetrics: (metrics: ObservationMetric[]) => void
  addMetric: (metric: ObservationMetric) => void
  setAlerts: (alerts: ObservationAlert[]) => void
  addAlert: (alert: ObservationAlert) => void
  acknowledgeAlert: (id: string) => void
  dismissAlert: (id: string) => void
  setObserving: (observing: boolean) => void
  reset: () => void
}

function generateId() {
  return `obs_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
}

const DEFAULT_CATEGORIES: ObservationCategory[] = [
  {
    id: "connector_health",
    label: "Connector Health",
    metrics: [],
    alerts: [],
  },
  {
    id: "mission_progress",
    label: "Mission Progress",
    metrics: [],
    alerts: [],
  },
  {
    id: "workflow_execution",
    label: "Workflow Execution",
    metrics: [],
    alerts: [],
  },
  {
    id: "runtime_metrics",
    label: "Runtime Metrics",
    metrics: [],
    alerts: [],
  },
]

export const useObservationStore = create<ObservationState>((set) => ({
  categories: DEFAULT_CATEGORIES,
  metrics: [],
  alerts: [],
  isObserving: false,
  lastUpdate: null,

  setCategories: (categories) => set({ categories }),

  updateCategory: (id, patch) =>
    set((s) => ({
      categories: s.categories.map((c) =>
        c.id === id ? { ...c, ...patch } : c
      ),
    })),

  setMetrics: (metrics) =>
    set({ metrics, lastUpdate: new Date().toISOString() }),

  addMetric: (metric) =>
    set((s) => ({
      metrics: [...s.metrics, metric].slice(-50),
      lastUpdate: new Date().toISOString(),
    })),

  setAlerts: (alerts) => set({ alerts }),

  addAlert: (alert) =>
    set((s) => ({
      alerts: [alert, ...s.alerts].slice(0, 100),
    })),

  acknowledgeAlert: (id) =>
    set((s) => ({
      alerts: s.alerts.map((a) =>
        a.id === id ? { ...a, acknowledged: true } : a
      ),
    })),

  dismissAlert: (id) =>
    set((s) => ({
      alerts: s.alerts.filter((a) => a.id !== id),
    })),

  setObserving: (observing) => set({ isObserving: observing }),

  reset: () => set({
    categories: DEFAULT_CATEGORIES,
    metrics: [],
    alerts: [],
    isObserving: false,
    lastUpdate: null,
  }),
}))
