"use client"
import { useEffect } from "react"
import { useCognitionStore } from "@/store/cognitionStore"
import { wsService } from "@/services/websocket"
import type { WSMessage } from "@/types/websocket"
import type { CognitionEvent } from "@/types/cognition"

// ==========================================
// USE COGNITION HOOK
// ==========================================

export function useCognition() {
    const store = useCognitionStore()

    useEffect((): (() => void) => {
        const unsub = wsService.subscribe((msg: WSMessage) => {
            if (!msg.agent || !msg.event_type) return

            const event: CognitionEvent = {
                agent:      msg.agent as string,
                event_type: msg.event_type as string,
                status:     (msg.status as string) ?? "info",
                message:    (msg.message as string) ?? "",
                timestamp:  (msg.timestamp as string) ?? new Date().toISOString(),
                phase:      msg.phase as string | undefined,
                stream_chunk:     msg.stream_chunk as string | undefined,
                stream_completed: msg.stream_completed as boolean | undefined,
            }

            store.addEvent(event)

            // Update node status
            store.updateAgentNode(event.agent.toLowerCase(), { status: "active" })

            if (event.stream_chunk) store.appendStream(event.stream_chunk)
            if (event.stream_completed) store.finalizeStream()
        })
        return unsub
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])

    return store
}
