import { api } from "@/services/api"

export interface CostAnomalyGap {
    gap: string
    severity: "low" | "medium" | "high" | "critical"
    description: string
}

export interface CostAnomalyCheck {
    provider: string
    today_cost: number
    gaps: CostAnomalyGap[]
    gap_signature: string
    severity: "low" | "medium" | "high" | "critical"
    ticket_key: string | null
    fix_applied: boolean
    checked_at: string
}

export interface DashboardCostAnomaly {
    recent: CostAnomalyCheck[]
    isPartialFailure: boolean
}

export async function fetchDashboardCostAnomaly(): Promise<DashboardCostAnomaly> {
    try {
        const response = await api.get<{ recent: CostAnomalyCheck[] }>(
            "/api/cost-anomaly/status",
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
