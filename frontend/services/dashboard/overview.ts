import { runtimeService } from "@/services/runtime"
import type { EmbeddingHealth } from "@/services/runtime"
import type { Mission } from "@/types/runtime"

export interface DashboardOverview {
    activeAgents:      number
    runningMissions:   number
    systemHealth:      "Excellent" | "Warning" | "Critical" | "Unknown"
    successRate:       number | null
    agentTrend:        string
    missionTrend:      string
    healthTrend:       string
    rateTrend:         string
    agentsSparkline:   number[]
    missionsSparkline: number[]
    healthSparkline:   number[]
    rateSparkline:     number[]
    degraded:          boolean
}

function computeSuccessRate(
    embedding: EmbeddingHealth | null,
    activeMissions: Mission[],
    completedMissions: Mission[],
): number | null {
    if (embedding) {
        const total = embedding.openai_calls + embedding.local_calls
        if (total > 0) {
            return Math.round(((total - embedding.failures) / total) * 1000) / 10
        }
    }
    const total = activeMissions.length + completedMissions.length
    if (total > 0) {
        return Math.round((completedMissions.length / total) * 1000) / 10
    }
    return null
}

function buildSparkline(value: number, count = 10): number[] {
    return Array.from({ length: count }, (_, i) => {
        const t = (i + 1) / count
        const noise = Math.sin(t * Math.PI * 2) * value * 0.05
        return Math.round(value + noise)
    })
}

export async function fetchDashboardOverview(): Promise<DashboardOverview> {
    const results = await Promise.allSettled([
        runtimeService.getHealth(),
        runtimeService.getAgents(),
        runtimeService.getActiveMissions(),
        runtimeService.getCompletedMissions(),
        runtimeService.getEmbeddingHealth(),
    ])

    const [healthResult, agentsResult, activeMissionsResult, completedMissionsResult, embeddingResult] = results

    const health = healthResult.status === "fulfilled" ? healthResult.value : null
    // /agents and /api/missions/active return dict-keyed collections
    // ({name: {...}}), not arrays — normalize to arrays via Object.values
    // so downstream .length / array logic works regardless of shape.
    const agents = agentsResult.status === "fulfilled" ? Object.values(agentsResult.value.registered_agents ?? {}) : []
    const activeMissions = activeMissionsResult.status === "fulfilled" ? Object.values(activeMissionsResult.value.active_missions ?? {}) : []
    const completedMissions = completedMissionsResult.status === "fulfilled" ? completedMissionsResult.value.completed_missions : []
    const embedding = embeddingResult.status === "fulfilled" ? embeddingResult.value : null

    const degraded = results.some((r) => r.status === "rejected")

    const activeAgentCount = agents.length
    const runningMissionCount = activeMissions.length
    const healthStatus = health?.status ?? "unknown"
    const systemHealth: DashboardOverview["systemHealth"] =
        healthStatus === "healthy" || healthStatus === "running"
            ? "Excellent"
            : healthStatus === "degraded"
                ? "Warning"
                : healthStatus === "critical" || healthStatus === "offline"
                    ? "Critical"
                    : "Unknown"

    const successRate = computeSuccessRate(embedding, activeMissions, completedMissions)
    const healthPct = systemHealth === "Excellent" ? 98 : systemHealth === "Warning" ? 75 : 40

    return {
        activeAgents:      activeAgentCount,
        runningMissions:   runningMissionCount,
        systemHealth,
        successRate,
        agentTrend:        `${activeAgentCount} registered`,
        missionTrend:      `${runningMissionCount} active`,
        healthTrend:       healthStatus === "healthy" ? "All systems operational" : `Status: ${healthStatus}`,
        rateTrend:         successRate != null ? `${successRate}% success` : "No data",
        agentsSparkline:   buildSparkline(activeAgentCount),
        missionsSparkline: buildSparkline(runningMissionCount),
        healthSparkline:   buildSparkline(healthPct),
        rateSparkline:     successRate != null ? buildSparkline(successRate) : buildSparkline(98),
        degraded,
    }
}
