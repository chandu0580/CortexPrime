import { api } from "@/services/api"

export interface IncidentSignal {
    source: "deploy_regression" | "flaky_test" | "rollback"
    summary: string
    severity: string
    detected_at: string
}

export interface CorrelatedIncident {
    incident_id: string
    service: string
    ticket_key: string | null
    signals: IncidentSignal[]
    suppressed_count: number
    hypothesis: string | null
    opened_at: string
    last_signal_at: string
}

export interface DashboardIncidents {
    recent: CorrelatedIncident[]
    isPartialFailure: boolean
}

export async function fetchDashboardIncidents(): Promise<DashboardIncidents> {
    try {
        const response = await api.get<{ recent: CorrelatedIncident[] }>(
            "/api/incidents",
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
