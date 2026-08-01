import { api } from "@/services/api"

export interface FlakyTestOccurrence {
    history_id: string
    service: string
    workflow_name: string
    run_key: string
    evidence: string
    hypothesis: string | null
    ticket_key: string | null
    detected_at: string
}

export interface PendingFlakyRetry {
    run_key: string
    service: string
    workflow_name: string
    triggered_at: string
}

export interface DashboardFlakyTests {
    pending: PendingFlakyRetry[]
    recent: FlakyTestOccurrence[]
    isPartialFailure: boolean
}

export async function fetchDashboardFlakyTests(): Promise<DashboardFlakyTests> {
    try {
        const response = await api.get<{ pending: PendingFlakyRetry[]; recent: FlakyTestOccurrence[] }>(
            "/api/flaky-tests",
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
