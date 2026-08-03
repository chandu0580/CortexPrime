import { api } from "@/services/api"

export interface DockerHealthGap {
    gap: string
    severity: "low" | "medium" | "high" | "critical"
    description: string
}

export interface DockerHealthCheck {
    container: string
    container_id: string
    gaps: DockerHealthGap[]
    gap_signature: string
    severity: "low" | "medium" | "high" | "critical"
    ticket_key: string | null
    fix_applied: boolean
    checked_at: string
}

export interface DashboardDockerHealth {
    recent: DockerHealthCheck[]
    isPartialFailure: boolean
}

export async function fetchDashboardDockerHealth(): Promise<DashboardDockerHealth> {
    try {
        const response = await api.get<{ recent: DockerHealthCheck[] }>(
            "/api/docker-health/status",
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
