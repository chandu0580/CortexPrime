import { create } from "zustand"

// ==========================================
// TELEMETRY + ACTIVITY TYPES
// ==========================================

export interface TelemetryPoint {
    t:          number   // sequence tick
    throughput: number   // tokens/sec
    latency:    number   // ms
    eventRate:  number   // events/sec
}

export type AgentActivityStatus = "idle" | "active" | "processing" | "done" | "error"

// ==========================================
// RUNTIME STORE
// ==========================================

interface RuntimeState {
    activeAgents:       number
    memoryUsage:        string
    runtimeStatus:      string
    websocketConnected: boolean
    totalEvents:        number
    latency:            string

    // Telemetry history for charts (last 30 points)
    telemetry:           TelemetryPoint[]
    cognitionThroughput: number

    // Live per-agent activity
    agentActivity:   Record<string, AgentActivityStatus>
    agentLastAction: Record<string, string>

    // Whether data is simulated (not from live WebSocket)
    isDemoMode: boolean

    // Actions
    setActiveAgents:        (count: number) => void
    setMemoryUsage:         (usage: string) => void
    setRuntimeStatus:       (status: string) => void
    setWebsocketConnected:  (connected: boolean) => void
    setIsDemoMode:          (demo: boolean) => void
    incrementEvents:        () => void
    setLatency:             (latency: string) => void
    addTelemetryPoint:      (point: TelemetryPoint) => void
    setAgentActivity:       (id: string, status: AgentActivityStatus, lastAction?: string) => void
}

export const useRuntimeStore = create<RuntimeState>((set) => ({
    activeAgents:       0,
    memoryUsage:        "—",
    runtimeStatus:      "connecting",
    websocketConnected: false,
    totalEvents:        0,
    latency:            "—",
    telemetry:          [],
    cognitionThroughput: 0,
    agentActivity: {
        orchestrator: "idle",
        planner:      "idle",
        research:     "idle",
        critic:       "idle",
        optimizer:    "idle",
        memory:       "idle",
    },
    agentLastAction: {},
    isDemoMode: true,

    setActiveAgents:       (count) => set({ activeAgents: count }),
    setMemoryUsage:        (usage) => set({ memoryUsage: usage }),
    setRuntimeStatus:      (status) => set({ runtimeStatus: status }),
    setWebsocketConnected: (connected) => set({ websocketConnected: connected }),
    setIsDemoMode:         (demo) => set({ isDemoMode: demo }),
    incrementEvents:       () => set((s) => {
        const total = s.totalEvents + 1
        // Derive activeAgents from activity map
        const active = Object.values(s.agentActivity).filter((st) => st === "active" || st === "processing").length
        return { totalEvents: total, activeAgents: active }
    }),
    setLatency: (latency) => set({ latency }),

    addTelemetryPoint: (point) =>
        set((s) => ({
            telemetry:           [...s.telemetry, point].slice(-40),
            cognitionThroughput: Math.round(point.throughput),
        })),

    setAgentActivity: (id, status, lastAction) =>
        set((s) => {
            const newActivity = { ...s.agentActivity, [id]: status }
            const active = Object.values(newActivity).filter((st) => st === "active" || st === "processing").length
            return {
                agentActivity:   newActivity,
                activeAgents:    active,
                agentLastAction: lastAction
                    ? { ...s.agentLastAction, [id]: lastAction }
                    : s.agentLastAction,
            }
        }),
}))