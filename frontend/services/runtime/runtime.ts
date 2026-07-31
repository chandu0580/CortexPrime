import { api } from "../api"
import type { RuntimeStatus, Mission, AutonomousLoop } from "@/types/runtime"

// ==========================================
// RUNTIME SERVICE
// ==========================================

export interface EmbeddingHealth {
    embedding_status:   "healthy" | "degraded" | "failed"
    active_model:       string
    expected_dimension: number
    actual_dimension:   number
    degraded_mode:      boolean
    cache_hits:         number
    cache_misses:       number
    openai_calls:       number
    local_calls:        number
    failures:           number
    mismatch_count:     number
    warning:            string | null
}

export const runtimeService = {
    getStatus:            () => api.get<RuntimeStatus>("/"),
    getHealth:            () => api.get<{ status: string }>("/health"),
    getAgents:            () => api.get<{ registered_agents: Record<string, unknown> }>("/agents"),
    getEvents:            () => api.get<{ events: unknown[] }>("/events"),
    getActiveMissions:    () => api.get<{ active_missions: Record<string, Mission> }>("/api/missions/active"),
    getCompletedMissions: () => api.get<{ completed_missions: Mission[] }>("/api/missions/completed"),
    getActiveLoops:       () => api.get<{ active_loops: AutonomousLoop[] }>("/api/orchestrator/loops/active"),
    getEmbeddingHealth:   () => api.get<EmbeddingHealth>("/health/embeddings"),
}
