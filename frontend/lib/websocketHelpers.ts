import type { WSMessage } from "@/types/websocket"

// ==========================================
// WEBSOCKET HELPERS
// ==========================================

export function parseWSMessage(raw: string): WSMessage | null {
    try {
        return JSON.parse(raw) as WSMessage
    } catch {
        return null
    }
}

export function isCognitionEvent(msg: WSMessage): boolean {
    return Boolean(msg.agent && msg.event_type && msg.message)
}

export function isStreamChunk(msg: WSMessage): boolean {
    return Boolean(msg.stream_chunk !== undefined)
}

export function isStreamComplete(msg: WSMessage): boolean {
    return Boolean(msg.stream_completed)
}

export function buildPingMessage(): string {
    return JSON.stringify({ type: "ping", timestamp: new Date().toISOString() })
}
