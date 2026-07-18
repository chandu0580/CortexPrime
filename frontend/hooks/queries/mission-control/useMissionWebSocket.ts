"use client"

import { useEffect, useRef } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { wsService } from "@/services/websocket"
import { queryKeys } from "@/lib/query"
import type { WSMessage } from "@/types/websocket"

export function useMissionWebSocket(enabled = true) {
    const queryClient = useQueryClient()
    const subscribed = useRef(false)

    useEffect(() => {
        if (!enabled || subscribed.current) return
        subscribed.current = true

        wsService.connect()

        const unsubscribe = wsService.subscribe((msg: WSMessage) => {
            const eventType = msg.type ?? msg.event_type

            if (!eventType) return

            if (eventType === "orchestration_update" || eventType === "mission_start" || eventType === "mission_complete" || eventType === "mission_failed") {
                queryClient.invalidateQueries({ queryKey: queryKeys.missionControl.missions() })
                queryClient.invalidateQueries({ queryKey: ["dashboard", "overview"] })
                queryClient.invalidateQueries({ queryKey: ["dashboard", "timeline"] })
                queryClient.invalidateQueries({ queryKey: ["workspace"] })
                return
            }

            if (eventType === "cognition_event" || eventType === "execution_event") {
                queryClient.invalidateQueries({ queryKey: queryKeys.missionControl.missions() })
                queryClient.invalidateQueries({ queryKey: [...queryKeys.missionControl.missions(), "events"] })
                return
            }

            if (eventType === "execution_state_update" || eventType === "pipeline_event") {
                queryClient.invalidateQueries({ queryKey: queryKeys.missionControl.missions() })
                if (msg.execution_id) {
                    queryClient.invalidateQueries({ queryKey: [...queryKeys.missionControl.all, "replay", msg.execution_id] })
                }
                return
            }

            if (eventType === "runtime_metrics" || eventType === "agent_telemetry") {
                queryClient.invalidateQueries({ queryKey: [...queryKeys.missionControl.missions(), "telemetry"] })
                return
            }
        })

        return () => {
            unsubscribe()
            subscribed.current = false
        }
    }, [enabled, queryClient])
}
