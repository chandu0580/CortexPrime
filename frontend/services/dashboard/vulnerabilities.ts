import { api } from "@/services/api"

export interface VulnerabilityCheck {
    history_id: string
    repo: string
    alert_number: number
    alert_key: string
    ghsa_id: string | null
    package: string
    severity: "low" | "medium" | "high" | "critical" | "unknown"
    summary: string
    state: string
    ticket_key: string | null
    checked_at: string
}

export interface DashboardVulnerabilities {
    latest: VulnerabilityCheck[]
    isPartialFailure: boolean
}

export async function fetchDashboardVulnerabilities(): Promise<DashboardVulnerabilities> {
    try {
        const response = await api.get<{ latest: VulnerabilityCheck[]; recent: VulnerabilityCheck[] }>(
            "/api/vulnerabilities/status",
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
