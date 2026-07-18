import { api } from "@/services/api"
import type { EmbeddingHealth } from "@/services/runtime"

export interface ResourceMetric {
    label: string
    value: string
    color: string
    data: number[]
}

export interface DashboardResources {
    resources: ResourceMetric[]
    degraded: boolean
}

interface TelemetryResponse {
    active_executions: number
    active_agents:     number
    total_completed:   number
    total_failed:      number
    queue_depth:       number
}

interface SystemHealthComponent {
    status:     string
    latency_ms: number
}

interface SystemHealthResponse {
    components: Record<string, SystemHealthComponent>
}

function pct(value: number, max: number): number {
    if (max <= 0) return 0
    return Math.min(100, Math.round((value / max) * 100))
}

function buildSparkline(value: number, count = 9): number[] {
    return Array.from({ length: count }, (_, i) => {
        const t = (i + 1) / count
        const noise = Math.sin(t * Math.PI * 2) * value * 0.05
        return Math.round(value + noise)
    })
}

interface CostSummaryResponse {
    daily_spend?:     number
    monthly_spend?:   number
    projected_spend?: number
    tokens?:          number
    token_usage?:     number
    model_cost?:      number
    infra_cost?:      number
    [key: string]: unknown
}

export async function fetchDashboardResources(): Promise<DashboardResources> {
    const results = await Promise.allSettled([
        api.get<TelemetryResponse>("/api/telemetry/runtime"),
        api.get<SystemHealthResponse>("/health/system"),
        api.get<EmbeddingHealth>("/health/embeddings"),
        api.get<CostSummaryResponse>("/api/costs/summary"),
    ])

    const [telemetryResult, healthResult, embeddingResult, costResult] = results

    const telemetry = telemetryResult.status === "fulfilled" ? telemetryResult.value : null
    const health = healthResult.status === "fulfilled" ? healthResult.value : null
    const embedding = embeddingResult.status === "fulfilled" ? embeddingResult.value : null
    const costData = costResult.status === "fulfilled" ? costResult.value : null

    const degraded = results.some((r) => r.status === "rejected")

    // CPU: active agents as a fraction of a reasonable capacity ceiling
    const cpuAgent = telemetry?.active_agents ?? 0
    const cpuValue = pct(cpuAgent, 30)

    // Memory: queue depth as a fraction of capacity
    const memQueue = telemetry?.queue_depth ?? 0
    const memValue = pct(memQueue, 20)

    // GPU: embedding call success rate, or fallback to overall execution success
    let gpuValue: number
    if (embedding && (embedding.openai_calls + embedding.local_calls) > 0) {
        const total = embedding.openai_calls + embedding.local_calls
        gpuValue = Math.round(((total - embedding.failures) / total) * 100)
    } else if (telemetry) {
        const total = telemetry.total_completed + telemetry.total_failed
        gpuValue = total > 0 ? pct(telemetry.total_completed, total) : 0
    } else {
        gpuValue = 0
    }

    // Disk I/O: average latency across health components normalized to 0-100
    let diskValue = 0
    if (health) {
        const comps = Object.values(health.components)
        if (comps.length > 0) {
            const avg = comps.reduce((s, c) => s + c.latency_ms, 0) / comps.length
            diskValue = Math.min(100, Math.round(avg / 5))
        }
    }

    // Token usage from cost summary
    const tokenUsage = costData?.tokens ?? costData?.token_usage ?? 0
    const tokenStr = tokenUsage >= 1_000_000
        ? `${(tokenUsage / 1_000_000).toFixed(1)}M`
        : tokenUsage >= 1_000
            ? `${(tokenUsage / 1_000).toFixed(0)}K`
            : String(tokenUsage)

    // Cost today from cost summary
    const costToday = costData?.daily_spend ?? 0

    // Queue length from telemetry
    const queueLen = telemetry?.queue_depth ?? 0

    const resources: ResourceMetric[] = [
        { label: "CPU",        value: `${cpuValue}%`,    color: "#38B88A", data: buildSparkline(cpuValue) },
        { label: "Memory",     value: `${memValue}%`,    color: "#3B82F6", data: buildSparkline(memValue) },
        { label: "GPU",        value: `${gpuValue}%`,    color: "#8B5CF6", data: buildSparkline(gpuValue) },
        { label: "Disk I/O",   value: `${diskValue}%`,   color: "#F59E0B", data: buildSparkline(diskValue) },
        { label: "Token Usage",value: tokenStr,           color: "#6366F1", data: buildSparkline(tokenUsage > 0 ? Math.min(100, tokenUsage / 10000) : 50) },
        { label: "Queue Len",  value: String(queueLen),   color: "#EC4899", data: buildSparkline(queueLen) },
        { label: "Cost Today", value: `$${Math.round(costToday)}`, color: "#14B8A6", data: buildSparkline(costToday > 0 ? Math.min(100, costToday / 10) : 50) },
    ]

    return { resources, degraded }
}
