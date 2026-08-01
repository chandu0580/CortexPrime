import { api } from "@/services/api"

export interface CredentialCheck {
    history_id: string
    connector_type: string
    valid: boolean
    expires_at: string | null
    expires_at_source: "api" | "advisory_header" | null
    days_until_expiry: number | null
    error: string | null
    ticket_key: string | null
    checked_at: string
}

export interface DashboardCredentials {
    latest: CredentialCheck[]
    isPartialFailure: boolean
}

export async function fetchDashboardCredentials(): Promise<DashboardCredentials> {
    try {
        const response = await api.get<{ latest: CredentialCheck[]; recent: CredentialCheck[] }>(
            "/api/credentials/status",
            { params: { limit: 8 } },
        )
        return {
            latest: response.latest ?? [],
            isPartialFailure: false,
        }
    } catch {
        return { latest: [], isPartialFailure: true }
    }
}
