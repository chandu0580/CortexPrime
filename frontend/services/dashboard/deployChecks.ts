import { api } from "@/services/api"

export interface DeployCheckRecord {
    history_id: string
    check_id: string
    service: string
    deployment_id: string
    regressed: boolean
    reasons: string[]
    ticket_key: string | null
    checked_at: string
}

export interface PendingDeployCheck {
    check_id: string
    service: string
    deployment_id: string
    check_due_at: string
}

export interface DashboardDeployChecks {
    pending: PendingDeployCheck[]
    recent: DeployCheckRecord[]
    isPartialFailure: boolean
}

export async function fetchDashboardDeployChecks(): Promise<DashboardDeployChecks> {
    try {
        const response = await api.get<{ pending: PendingDeployCheck[]; recent: DeployCheckRecord[] }>(
            "/api/github/deploy-checks",
            { params: { limit: 8 } },
        )
        return {
            pending: response.pending ?? [],
            recent: response.recent ?? [],
            isPartialFailure: false,
        }
    } catch {
        return { pending: [], recent: [], isPartialFailure: true }
    }
}
