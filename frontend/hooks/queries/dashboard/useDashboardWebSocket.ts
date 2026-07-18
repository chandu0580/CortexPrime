"use client"

import { useEffect, useRef } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { wsService } from "@/services/websocket"
import type { WSMessage } from "@/types/websocket"

const EVENT_TYPE_TO_KEY: Record<string, string[]> = {
    cognition_event:      ["dashboard", "events"],
    execution_event:      ["dashboard", "timeline"],
    orchestration_update: ["dashboard", "timeline", "dashboard", "overview"],
    agent_status_update:  ["dashboard", "agents"],
    runtime_metrics:      ["dashboard", "resources"],
    health_update:        ["dashboard", "health"],
    system:               ["dashboard", "health"],
}

const EXECUTIVE_DASHBOARD_TRIGGERS = new Set([
    "cognition_event",
    "execution_event",
    "orchestration_update",
    "agent_status_update",
    "runtime_metrics",
    "health_update",
    "system",
])

export function useDashboardWebSocket(enabled = true) {
    const queryClient = useQueryClient()
    const subscribed = useRef(false)

    useEffect(() => {
        if (!enabled || subscribed.current) return
        subscribed.current = true

        wsService.connect()

        const unsubscribe = wsService.subscribe((msg: WSMessage) => {
            const eventType = msg.type ?? msg.event_type
            if (!eventType) return

            const keys = EVENT_TYPE_TO_KEY[eventType]
            if (keys) {
                const seen = new Set<string>()
                for (const key of keys) {
                    if (!seen.has(key)) {
                        seen.add(key)
                        queryClient.invalidateQueries({ queryKey: [key] })
                    }
                }
                return
            }

            if (eventType === "cognition_event" || eventType === "execution_event") {
                queryClient.invalidateQueries({ queryKey: ["dashboard", "events"] })
                queryClient.invalidateQueries({ queryKey: ["dashboard", "timeline"] })
                return
            }

            if (eventType === "orchestration_update" || eventType === "agent_status_update") {
                queryClient.invalidateQueries({ queryKey: ["dashboard", "overview"] })
                queryClient.invalidateQueries({ queryKey: ["dashboard", "agents"] })
                queryClient.invalidateQueries({ queryKey: ["dashboard", "timeline"] })
                return
            }

            if (eventType === "runtime_metrics" || eventType === "system" || eventType === "health_update") {
                queryClient.invalidateQueries({ queryKey: ["dashboard", "resources"] })
                queryClient.invalidateQueries({ queryKey: ["dashboard", "health"] })
            }

            if (EXECUTIVE_DASHBOARD_TRIGGERS.has(eventType)) {
                queryClient.invalidateQueries({ queryKey: ["executiveDashboard"] })
            }
        })

        return () => {
            unsubscribe()
            subscribed.current = false
        }
    }, [enabled, queryClient])
}
