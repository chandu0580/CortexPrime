// ==========================================
// RUNTIME TYPES
// ==========================================

export interface RuntimeStatus {
    status: "running" | "idle" | "degraded" | "offline"
    version: string
    uptime: number
    registeredAgents: string[]
}

export interface AgentMeta {
    id: string
    name: string
    status: "active" | "idle" | "error"
    tasksCompleted: number
    latencyMs: number
}

export interface Mission {
    id: string
    goal: string
    status: "active" | "completed" | "failed" | "pending"
    createdAt: string
    completedAt?: string
    agentsInvolved: string[]
    result?: string
}

export interface RuntimeEvent {
    id: string
    type: string
    agent: string
    message: string
    timestamp: string
    payload?: Record<string, unknown>
}

export interface RuntimeMetrics {
    activeAgents: number
    memoryUsageMb: number
    latencyMs: number
    totalEvents: number
    websocketConnected: boolean
    runtimeStatus: string
}

export interface AutonomousLoop {
    id: string
    status: "running" | "paused" | "stopped"
    iteration: number
    goal: string
    startedAt: string
}
