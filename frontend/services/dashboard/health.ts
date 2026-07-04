import { api } from "@/services/api"

export interface ServiceHealthInfo {
    label:  string
    status: "healthy" | "warning" | "unavailable" | "unknown"
}

export interface DashboardHealth {
    overallHealth: number
    services: ServiceHealthInfo[]
    degraded: boolean
}

interface SystemHealthComponent {
    status:  string
    latency_ms: number
    detail?: Record<string, unknown>
}

interface SystemHealthResponse {
    status:      string
    components:  Record<string, SystemHealthComponent>
}

const SERVICE_LABELS: Record<string, string> = {
    postgres:      "Database",
    redis:         "Redis Cache",
    rabbitmq:      "Message Queue",
    embeddings:    "Vector Store",
    auth:          "API Services",
    llm:           "Voice Services",
}

function mapStatus(raw: string): ServiceHealthInfo["status"] {
    switch (raw) {
        case "healthy":     return "healthy"
        case "degraded":    return "warning"
        case "offline":
        case "unavailable": return "unavailable"
        default:            return "unknown"
    }
}

function computeOverall(components: Record<string, SystemHealthComponent>): number {
    const entries = Object.entries(components)
    if (entries.length === 0) return 0
    let total = 0
    for (const [, c] of entries) {
        if (c.status === "healthy")    total += 100
        else if (c.status === "degraded") total += 50
    }
    return Math.round(total / entries.length)
}

const DISPLAY_SERVICES = ["postgres", "redis", "rabbitmq", "embeddings", "auth", "llm"] as const

export async function fetchDashboardHealth(): Promise<DashboardHealth> {
    const response = await api.get<SystemHealthResponse>("/health/system")
    const components = response.components ?? {}

    const services: ServiceHealthInfo[] = DISPLAY_SERVICES.map((key) => {
        const comp = components[key]
        if (!comp) return { label: SERVICE_LABELS[key], status: "unknown" }
        return { label: SERVICE_LABELS[key], status: mapStatus(comp.status) }
    })

    const overallHealth = computeOverall(components)

    return {
        overallHealth,
        services,
        degraded: Object.values(components).some(
            (c) => c.status === "degraded" || c.status === "offline" || c.status === "unavailable",
        ),
    }
}
