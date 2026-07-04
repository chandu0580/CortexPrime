// ==========================================
// COGNITION TYPES
// ==========================================

export interface CognitionEvent {
    event_id?: string
    agent: string
    event_type: string
    // alias fields used by legacy components
    type?:  string
    event?: string
    status: string
    message: string
    timestamp: string
    phase?: string
    stream?: boolean
    stream_chunk?: string
    stream_completed?: boolean
    execution_id?: string
    retry_count?: number
    orchestration_depth?: number
    sources?: CognitionSource[]
    payload?: Record<string, unknown>
}

export interface CognitionSource {
    title?: string
    url?: string
    content?: string
    score?: number
}

export interface AgentNode {
    id: string
    label: string
    status: "active" | "idle" | "processing" | "done" | "error"
    type: "orchestrator" | "planner" | "research" | "critic" | "optimizer" | "memory"
    x?: number
    y?: number
}

export interface AgentEdge {
    id: string
    source: string
    target: string
    label?: string
    animated?: boolean
}

export interface CognitionPhase {
    phase: string
    agent: string
    status: "pending" | "active" | "complete"
    startedAt?: string
    completedAt?: string
}

export interface ExecutionTrace {
    execution_id: string
    goal: string
    phases: CognitionPhase[]
    startedAt: string
    completedAt?: string
    result?: string
}
