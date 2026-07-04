import { api } from "../api"

// ==========================================
// COGNITION SERVICE
// ==========================================

export const cognitionService = {
    execute: (payload: { objective: string }) =>
        api.post("/orchestrate", payload),

    executeAutonomous: (payload: { objective: string; [k: string]: unknown }) =>
        api.post("/api/orchestrator/autonomous", payload),

    executeGoal: (payload: { objective: string }) =>
        api.post("/api/orchestrator/execute", payload),

    reflect: (payload: unknown) =>
        api.post("/api/orchestrator/reflect", payload),
}
