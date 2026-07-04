import { WS_URL, WS_RECONNECT_INTERVAL_MS, WS_MAX_RECONNECT_ATTEMPTS } from "@/lib/constants"
import { parseWSMessage } from "@/lib/websocketHelpers"
import type { WSMessage } from "@/types/websocket"

// ==========================================
// WEBSOCKET SERVICE
// ==========================================

type MessageHandler = (msg: WSMessage) => void

class WebSocketService {
    private ws:           WebSocket | null = null
    private handlers:     Set<MessageHandler> = new Set()
    private reconnects  = 0
    private reconnectTimer: ReturnType<typeof setTimeout> | null = null
    private _connected  = false
    // Unique session ID for this browser tab — used to route stream events
    private _sessionId: string = typeof crypto !== "undefined"
        ? crypto.randomUUID()
        : `session-${Date.now()}-${Math.random().toString(36).slice(2)}`

    get connected() { return this._connected }

    getSessionId(): string { return this._sessionId }

    connect(url = WS_URL) {
        if (this.ws?.readyState === WebSocket.OPEN) return
        // Cookie auth is sent by the browser during WS handshake.
        const params = new URLSearchParams()
        params.set("session_id", this._sessionId)

        const urlWithParams = `${url}?${params.toString()}`
        this.ws = new WebSocket(urlWithParams)

        this.ws.onopen = () => {
            this._connected = true
            this.reconnects = 0
        }

        this.ws.onmessage = (e) => {
            const msg = parseWSMessage(e.data as string)
            if (msg) this.handlers.forEach((h) => h(msg))
        }

        this.ws.onclose = () => {
            this._connected = false
            this.scheduleReconnect(url)
        }

        this.ws.onerror = () => {
            this.ws?.close()
        }
    }

    private scheduleReconnect(url: string) {
        if (this.reconnects >= WS_MAX_RECONNECT_ATTEMPTS) return
        this.reconnectTimer = setTimeout(() => {
            this.reconnects++
            this.connect(url)
        }, WS_RECONNECT_INTERVAL_MS)
    }

    subscribe(handler: MessageHandler) {
        this.handlers.add(handler)
        return () => this.handlers.delete(handler)
    }

    /** Re-open the connection (e.g., after a token refresh). */
    reconnect(url = WS_URL) {
        if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
        this.ws?.close()
        this.ws = null
        this._connected = false
        this.connect(url)
    }

    send(payload: unknown) {
        if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(payload))
        }
    }

    disconnect() {
        if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
        this.ws?.close()
        this.ws = null
        this._connected = false
    }
}

export const wsService = new WebSocketService()
