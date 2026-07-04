"use client"
import { useEffect } from "react"
import { useMemoryStore } from "@/store/memoryStore"
import { memoryService } from "@/services/memory"

// ==========================================
// USE MEMORY HOOK
// ==========================================

export function useMemory(autoQuery?: string) {
    const store = useMemoryStore()

    useEffect(() => {
        if (!autoQuery) return
        store.setLoading(true)
        memoryService.recallEpisodic(autoQuery)
            .then((r) => store.setEntries(r.memories ?? []))
            .catch(() => {})
            .finally(() => store.setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [autoQuery])

    return store
}
