import { api } from "@/services/api"

export interface RollbackAttempt {
    history_id: string
    provider: "github" | "gitlab"
    service: string
    environment: string
    bad_deployment_id: string
    reasons: string[]
    triggered: boolean
    target_sha: string | null
    target_deployment_id: string | number | null
    rollback_deployment_id: string | number | null
    ticket_key: string | null
    error: string | null
    triggered_at: string
}

export interface DashboardRollbacks {
    recent: RollbackAttempt[]
    isPartialFailure: boolean
}

export async function fetchDashboardRollbacks(): Promise<DashboardRollbacks> {
    try {
        const response = await api.get<{ recent: RollbackAttempt[] }>(
            "/api/rollbacks",
            { params: { limit: 8 } },
        )
        return {
            recent: response.recent ?? [],
            isPartialFailure: false,
        }
    } catch {
        return { recent: [], isPartialFailure: true }
    }
}
