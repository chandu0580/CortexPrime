"use client"
import { useEffect, useRef } from "react"
import { useRuntimeStore } from "@/store/runtimeStore"
import { runtimeService } from "@/services/runtime"
import { POLL_INTERVAL_MS } from "@/lib/constants"

// ==========================================
// USE RUNTIME HOOK
// ==========================================

export function useRuntime() {
    const store  = useRuntimeStore()
    const timer  = useRef<ReturnType<typeof setInterval> | null>(null)

    useEffect(() => {
        const poll = async () => {
            try {
                const health = await runtimeService.getHealth()
                store.setRuntimeStatus(health.status ?? "unknown")
            } catch {
                store.setRuntimeStatus("offline")
            }
        }

        poll()
        timer.current = setInterval(poll, POLL_INTERVAL_MS)
        return () => { if (timer.current) clearInterval(timer.current) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])

    return store
}
