import { api } from "../api"
import type { MemoryEntry } from "@/types/memory"

// ==========================================
// MEMORY SERVICE
// ==========================================

export const memoryService = {
    storeEpisodic: (payload: { content: string; context?: string }) =>
        api.post("/memory/episodic/store", payload),

    recallEpisodic: (query: string) =>
        api.post<{ memories: MemoryEntry[] }>("/memory/episodic/recall", { query }),

    reflect: (payload: unknown) =>
        api.post("/memory/episodic/reflect", payload),
}
