import { runtimeService } from "@/services/runtime"

export interface DashboardTimelineItem {
    id: string
    name: string
    status: "queued" | "running" | "completed" | "failed"
    progress: number | null
    startedAt: Date | null
    completedAt: Date | null
    duration: string | null
    assignedAgent?: string
}

export interface DashboardTimeline {
    items: DashboardTimelineItem[]
    tlPoints: { x: number; y: number }[]
    isPartialFailure: boolean
}

const MAX_DISPLAY = 5
const ESTIMATED_MISSION_MS = 5 * 60 * 1000

function computeProgress(
    status: DashboardTimelineItem["status"],
    startedAt: Date | null,
    completedAt: Date | null,
): number | null {
    if (status === "completed" || status === "failed") return 100
    if (status === "queued") return 0
    if (!startedAt) return null

    const elapsed = Date.now() - startedAt.getTime()
    const raw = Math.round((elapsed / ESTIMATED_MISSION_MS) * 100)
    return Math.min(Math.max(raw, 0), 99)
}

function formatDuration(startedAt: Date | null, completedAt: Date | null): string | null {
    if (!startedAt) return null

    const end = completedAt ?? new Date()
    const ms = end.getTime() - startedAt.getTime()
    if (ms < 1000) return "<1s"

    const totalSeconds = Math.floor(ms / 1000)
    const hours = Math.floor(totalSeconds / 3600)
    const minutes = Math.floor((totalSeconds % 3600) / 60)
    const seconds = totalSeconds % 60

    const parts: string[] = []
    if (hours > 0) parts.push(`${hours}h`)
    if (minutes > 0) parts.push(`${minutes}m`)
    if (seconds > 0 && hours === 0) parts.push(`${seconds}s`)
    return parts.join(" ") || "<1s"
}

function parseDate(value: unknown): Date | null {
    if (typeof value === "string") {
        const d = new Date(value)
        return Number.isFinite(d.getTime()) ? d : null
    }
    return null
}

function normalizeStatus(raw: unknown): DashboardTimelineItem["status"] {
    if (typeof raw !== "string") return "queued"
    const s = raw.toLowerCase()
    if (s === "active" || s === "running" || s === "in_progress") return "running"
    if (s === "completed" || s === "complete") return "completed"
    if (s === "failed" || s === "error" || s === "cancelled") return "failed"
    if (s === "pending" || s === "queued") return "queued"
    return "running"
}

function pickFirstAgent(raw: unknown): string | undefined {
    if (Array.isArray(raw) && raw.length > 0 && typeof raw[0] === "string") {
        return raw[0]
    }
    return undefined
}

function generateTimelinePoints(count: number): { x: number; y: number }[] {
    if (count === 0) return []
    const w = 185
    const step = w / (count + 1)
    const mid = 65
    return Array.from({ length: count }, (_, i) => ({
        x: Math.round(step * (i + 1)),
        y: mid + Math.round((i - (count - 1) / 2) * 12),
    }))
}

function extractMissions(raw: unknown): DashboardTimelineItem[] {
    const items: DashboardTimelineItem[] = []
    if (!raw || typeof raw !== "object") return items

    const body = raw as Record<string, unknown>

    const activeMissions = body["active_missions"]
    if (activeMissions && typeof activeMissions === "object" && !Array.isArray(activeMissions)) {
        for (const [execId, entry] of Object.entries(activeMissions)) {
            if (!entry || typeof entry !== "object") continue
            const e = entry as Record<string, unknown>
            const startedAt = parseDate(e["started_at"] ?? e["createdAt"])
            const status = normalizeStatus(e["status"])
            items.push({
                id: execId,
                name: typeof e["goal"] === "string" ? e["goal"] : execId,
                status,
                progress: computeProgress(status, startedAt, null),
                startedAt,
                completedAt: null,
                duration: formatDuration(startedAt, null),
                assignedAgent: pickFirstAgent(e["agentsInvolved"]),
            })
        }
    }

    const completedMissions = body["completed_missions"]
    if (Array.isArray(completedMissions)) {
        for (const entry of completedMissions) {
            if (!entry || typeof entry !== "object") continue
            const e = entry as Record<string, unknown>
            const execId = typeof e["execution_id"] === "string" ? e["execution_id"]
                : typeof e["id"] === "string" ? e["id"]
                : `completed-${Math.random().toString(36).slice(2, 8)}`
            const startedAt = parseDate(e["started_at"] ?? e["createdAt"] ?? e["startedAt"])
            const completedAt = parseDate(e["completed_at"] ?? e["completedAt"])
            const status = normalizeStatus(e["status"])
            items.push({
                id: execId,
                name: typeof e["goal"] === "string" ? e["goal"] : execId,
                status: status === "running" ? "completed" : status,
                progress: 100,
                startedAt,
                completedAt,
                duration: formatDuration(startedAt, completedAt),
                assignedAgent: pickFirstAgent(e["agentsInvolved"]),
            })
        }
    }

    return items
}

export async function fetchDashboardTimeline(): Promise<DashboardTimeline> {
    const results = await Promise.allSettled([
        runtimeService.getActiveMissions(),
        runtimeService.getCompletedMissions(),
    ])

    const items: DashboardTimelineItem[] = []

    for (const result of results) {
        if (result.status === "fulfilled") {
            items.push(...extractMissions(result.value))
        }
    }

    items.sort((a, b) => {
        const ta = a.startedAt?.getTime() ?? 0
        const tb = b.startedAt?.getTime() ?? 0
        return tb - ta
    })

    const sliced = items.slice(0, MAX_DISPLAY)

    return {
        items: sliced,
        tlPoints: generateTimelinePoints(sliced.length),
        isPartialFailure: results.some((r) => r.status === "rejected"),
    }
}
