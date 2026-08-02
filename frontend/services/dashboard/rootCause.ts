import { api } from "@/services/api"

export interface RootCauseTopCause {
    cause: string
    count: number
}

export interface RootCauseRecentAnalysis {
    analysis_id: string
    problem: string
    root_cause: string
    confidence: number
    timestamp: string
}

export interface DashboardRootCause {
    totalAnalyses: number
    totalIncidents: number
    avgConfidence: number
    topRootCauses: RootCauseTopCause[]
    recentAnalyses: RootCauseRecentAnalysis[]
    isPartialFailure: boolean
}

export async function fetchDashboardRootCause(): Promise<DashboardRootCause> {
    try {
        const response = await api.get<{
            total_analyses: number
            total_incidents: number
            avg_confidence: number
            top_root_causes: RootCauseTopCause[]
            recent_analyses: RootCauseRecentAnalysis[]
        }>("/api/rca/dashboard")
        return {
            totalAnalyses: response.total_analyses ?? 0,
            totalIncidents: response.total_incidents ?? 0,
            avgConfidence: response.avg_confidence ?? 0,
            topRootCauses: response.top_root_causes ?? [],
            recentAnalyses: response.recent_analyses ?? [],
            isPartialFailure: false,
        }
    } catch {
        return {
            totalAnalyses: 0, totalIncidents: 0, avgConfidence: 0,
            topRootCauses: [], recentAnalyses: [], isPartialFailure: true,
        }
    }
}
