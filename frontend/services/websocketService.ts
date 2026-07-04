
export interface CognitionSource {

    title?: string

    url?: string

    content?: string

    score?: number
}


// ==========================================
// COGNITION EVENT
// ==========================================

export interface CognitionEvent {

    // ==========================================
    // CORE
    // ==========================================

    event_id?: string

    agent: string

    event_type: string

    // legacy alias fields used by pre-existing components
    type?:  string

    event?: string

    status: string

    message: string

    timestamp: string

    // ==========================================
    // COGNITION PHASE
    // ==========================================

    phase?: string

    // ==========================================
    // STREAMING
    // ==========================================

    stream?: boolean

    stream_chunk?: string

    stream_completed?: boolean

    // ==========================================
    // EXECUTION
    // ==========================================

    execution_id?: string

    retry_count?: number

    orchestration_depth?: number

    // ==========================================
    // PERFORMANCE
    // ==========================================

    latency_ms?: number

    token_usage?: any

    // ==========================================
    // GOVERNANCE
    // ==========================================

    confidence_score?: number

    hallucination_score?: number

    governance_status?: string

    // ==========================================
    // SWARM INTELLIGENCE
    // ==========================================

    consensus_score?: number

    debate_round?: number

    participating_agents?: string[]

    // ==========================================
    // PAYLOAD
    // ==========================================

    payload?: any

    sources?: CognitionSource[]
}


// ==========================================
// WEBSOCKET SERVICE
// ==========================================

class WebSocketService {

    // ==========================================
    // SOCKET
    // ==========================================

    private socket: WebSocket | null =
        null

    // ==========================================
    // LISTENERS
    // ==========================================

    private listeners: Array<
        (event: CognitionEvent) => void
    > = []


    // ==========================================
    // CONNECT
    // ==========================================

    connect() {

        // ==========================================
        // PREVENT DUPLICATE CONNECTIONS
        // ==========================================

        if (

            this.socket &&

            (
                this.socket.readyState ===
                WebSocket.OPEN

                ||

                this.socket.readyState ===
                WebSocket.CONNECTING
            )
        ) {

            return
        }

        // ==========================================
        // CREATE SOCKET
        // ==========================================

        this.socket = new WebSocket(

            "ws://127.0.0.1:8000/ws"
        )

        // ==========================================
        // OPEN
        // ==========================================

        this.socket.onopen = () => {

            console.log(

                "🧠 CortexPrime WebSocket Connected"
            )
        }

        // ==========================================
        // MESSAGE
        // ==========================================

        this.socket.onmessage = (

            event
        ) => {

            try {

                const parsedEvent:
                    CognitionEvent =

                    JSON.parse(
                        event.data
                    )

                // ==========================================
                // NOTIFY LISTENERS
                // ==========================================

                this.listeners.forEach(

                    (listener) => {

                        try {

                            listener(
                                parsedEvent
                            )

                        } catch (listenerError) {

                            console.error(

                                "Listener Error:",

                                listenerError
                            )
                        }
                    }
                )

            } catch (error) {

                console.error(

                    "WebSocket Parse Error:",

                    error
                )
            }
        }

        // ==========================================
        // CLOSE
        // ==========================================

        this.socket.onclose = () => {

            console.log(

                "🔌 WebSocket Disconnected"
            )

            this.socket = null
        }

        // ==========================================
        // ERROR
        // ==========================================

        this.socket.onerror = (

            error
        ) => {

            console.error(

                "🚨 WebSocket Error:",

                error
            )
        }
    }


    // ==========================================
    // SUBSCRIBE
    // ==========================================

    subscribe(

        callback: (
            event: CognitionEvent
        ) => void

    ) {

        // ==========================================
        // PREVENT DUPLICATE LISTENERS
        // ==========================================

        const exists = this.listeners.includes(
            callback
        )

        if (!exists) {

            this.listeners.push(
                callback
            )
        }
    }


    // ==========================================
    // UNSUBSCRIBE
    // ==========================================

    unsubscribe(

        callback: (
            event: CognitionEvent
        ) => void

    ) {

        this.listeners = (

            this.listeners.filter(

                (listener) =>

                    listener !== callback
            )
        )
    }


    // ==========================================
    // DISCONNECT
    // ==========================================

    disconnect() {

        if (this.socket) {

            this.socket.close()

            this.socket = null
        }

        // ==========================================
        // CLEAR LISTENERS
        // ==========================================

        this.listeners = []
    }
}


// ==========================================
// SINGLETON
// ==========================================

export const websocketService =
    new WebSocketService()
