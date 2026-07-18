"use client"
import { useEffect, useRef, useState } from "react"
import { wsService } from "@/services/websocket"
import { WS_URL } from "@/lib/constants"
import type { WSStatus } from "@/types/websocket"

// ==========================================
// USE REALTIME HOOK
// ==========================================

export function useRealtime() {
    const [status, setStatus] = useState<WSStatus>("disconnected")
    const connected = useRef(false)

    useEffect(() => {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setStatus("connecting")
        wsService.connect(WS_URL)

        const checkTimer = setInterval(() => {
            const now = wsService.connected
            if (now !== connected.current) {
                connected.current = now
                setStatus(now ? "connected" : "disconnected")
            }
        }, 1000)

        return () => {
            clearInterval(checkTimer)
            wsService.disconnect()
        }
    }, [])

    return { status, send: wsService.send.bind(wsService) }
}
