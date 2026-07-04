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

function sparkline(base: number, count = 10): number[] {
    const pts: number[] = []
    let v = base * (0.85 + Math.random() * 0.3)
    for (let i = 0; i < count; i++) {
        v = Math.max(1, v + (Math.random() - 0.5) * v * 0.15)
        pts.push(Math.round(v * 10) / 10)
    }
    return pts
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
    const agents = agentsResult.status === "fulfilled" ? agentsResult.value.registered_agents : []
    const activeMissions = activeMissionsResult.status === "fulfilled" ? activeMissionsResult.value.active_missions : []
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

    return {
        activeAgents:      activeAgentCount,
        runningMissions:   runningMissionCount,
        systemHealth,
        successRate,
        agentTrend:        `${activeAgentCount} registered`,
        missionTrend:      `${runningMissionCount} active`,
        healthTrend:       healthStatus === "healthy" ? "All systems operational" : `Status: ${healthStatus}`,
        rateTrend:         successRate != null ? `${successRate}% success` : "No data",
        agentsSparkline:   sparkline(activeAgentCount),
        missionsSparkline: sparkline(runningMissionCount),
        healthSparkline:   [96, 97, 97, 98, 97, 98, 99, 98, 99, 100],
        rateSparkline:     successRate != null ? sparkline(successRate) : [95, 96, 95, 97, 96, 97, 98, 97, 98, 98],
        degraded,
    }
}
