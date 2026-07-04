import { api } from "@/services/api"
import { runtimeService } from "@/services/runtime"

export interface HeaderUser {
    name: string
    role: string
}

export interface HeaderStatus {
    currentMission: string | null
    missionState: "running" | "idle" | "completed" | "unknown"
    runtimeStatus: "healthy" | "degraded" | "offline"
    voiceConnected: boolean
    notificationCount: number
    currentUser: HeaderUser | null
}

export interface DashboardHeader {
    header: HeaderStatus
    isPartialFailure: boolean
}

function parseMissionState(raw: string): HeaderStatus["missionState"] {
    const s = raw.toLowerCase()
    if (s === "running" || s === "active" || s === "in_progress") return "running"
    if (s === "completed" || s === "complete") return "completed"
    if (s === "idle" || s === "pending" || s === "queued") return "idle"
    return "unknown"
}

function parseRuntimeStatus(raw: string): HeaderStatus["runtimeStatus"] {
    const s = raw.toLowerCase()
    if (s === "healthy" || s === "running" || s === "ok") return "healthy"
    if (s === "degraded" || s === "warning") return "degraded"
    return "offline"
}

function deriveDisplayName(raw: unknown): string {
    if (typeof raw !== "string") return "Operator"
    if (raw.includes("@")) return raw.split("@")[0]
    return raw.charAt(0).toUpperCase() + raw.slice(1)
}

function deriveDisplayRole(raw: unknown): string {
    if (typeof raw !== "string") return "Operator"
    const r = raw.toUpperCase()
    if (r === "ADMIN") return "Administrator"
    if (r === "OPERATOR") return "Operator"
    if (r === "VIEWER") return "Viewer"
    return r.charAt(0) + r.slice(1).toLowerCase()
}

export async function fetchDashboardHeader(): Promise<DashboardHeader> {
    const results = await Promise.allSettled([
        runtimeService.getActiveMissions(),
        runtimeService.getHealth(),
        api.get<Record<string, unknown>>("/api/voice/v2/health"),
        api.get<Record<string, unknown>>("/api/auth/me"),
        runtimeService.getEvents(),
    ])

    const isPartialFailure = results.some((r) => r.status === "rejected")

    const [missionRes, healthRes, voiceRes, userRes, eventsRes] = results

    let currentMission: string | null = null
    let missionState: HeaderStatus["missionState"] = "unknown"

    if (missionRes.status === "fulfilled") {
        const raw = missionRes.value as unknown as Record<string, unknown>
        const missions = raw["active_missions"]
        if (missions && typeof missions === "object" && !Array.isArray(missions)) {
            const entries = Object.entries(missions)
            if (entries.length > 0) {
                const first = entries[0][1] as Record<string, unknown>
                currentMission = typeof first["goal"] === "string" ? first["goal"] : null
                missionState = parseMissionState(String(first["status"] ?? "unknown"))
            }
        }
    }

    let runtimeStatus: HeaderStatus["runtimeStatus"] = "healthy"
    if (healthRes.status === "fulfilled") {
        runtimeStatus = parseRuntimeStatus(String(healthRes.value.status ?? ""))
    }

    let voiceConnected = false
    if (voiceRes.status === "fulfilled") {
        const s = String(voiceRes.value["status"] ?? "")
        const livekit = voiceRes.value["livekit"]
        voiceConnected = s === "ok" && livekit === true
    }

    let currentUser: HeaderUser | null = null
    if (userRes.status === "fulfilled") {
        const id = userRes.value["user_id"]
        const role = userRes.value["role"]
        if (id || role) {
            currentUser = {
                name: deriveDisplayName(id),
                role: deriveDisplayRole(role),
            }
        }
    }

    let notificationCount = 0
    if (eventsRes.status === "fulfilled") {
        const rawList = eventsRes.value["events"]
        if (Array.isArray(rawList)) {
            for (const entry of rawList.slice(-50)) {
                if (entry && typeof entry === "object") {
                    const e = entry as Record<string, unknown>
                    const status = String(e["status"] ?? "").toLowerCase()
                    if (status === "failed" || status === "error" || status === "blocked" || status === "rejected") {
                        notificationCount++
                    }
                }
            }
        }
    }

    return {
        header: {
            currentMission,
            missionState,
            runtimeStatus,
            voiceConnected,
            notificationCount,
            currentUser,
        },
        isPartialFailure,
    }
}
