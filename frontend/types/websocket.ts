// ==========================================
// WEBSOCKET TYPES
// ==========================================

export type WSStatus = "connecting" | "connected" | "disconnected" | "error"

export interface WSMessage {
    type: string
    agent?: string
    event_type?: string
    status?: string
    message?: string
    timestamp?: string
    payload?: Record<string, unknown>
    stream_chunk?: string
    stream_completed?: boolean
    [key: string]: unknown
}

export interface WSConfig {
    url: string
    reconnectIntervalMs: number
    maxReconnectAttempts: number
    pingIntervalMs: number
}

export interface WSConnectionState {
    status: WSStatus
    reconnectAttempts: number
    lastConnectedAt?: string
    lastMessageAt?: string
}
