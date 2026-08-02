import { api } from "@/services/api"

export interface BranchProtectionGap {
    gap: string
    severity: "low" | "medium" | "high" | "critical"
    description: string
}

export interface BranchProtectionCheck {
    repo: string
    branch: string
    gaps: BranchProtectionGap[]
    gap_signature: string
    severity: "low" | "medium" | "high" | "critical" | "unknown"
    ticket_key: string | null
    fix_applied: boolean
    error: string | null
    checked_at: string
}

export interface DashboardBranchProtection {
    recent: BranchProtectionCheck[]
    isPartialFailure: boolean
}

export async function fetchDashboardBranchProtection(): Promise<DashboardBranchProtection> {
    try {
        const response = await api.get<{ recent: BranchProtectionCheck[] }>(
            "/api/branch-protection/status",
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
