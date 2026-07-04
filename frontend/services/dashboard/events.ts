import { runtimeService } from "@/services/runtime"

export type DashboardEventType =
    | "mission"
    | "runtime"
    | "agent"
    | "voice"
    | "browser"
    | "computer"
    | "research"
    | "governance"
    | "system"

export type DashboardEventSeverity =
    | "info"
    | "success"
    | "warning"
    | "error"

export interface DashboardEvent {
    id: string
    timestamp: Date
    type: DashboardEventType
    title: string
    description: string
    severity: DashboardEventSeverity
    source: string
}

export interface DashboardEvents {
    items: DashboardEvent[]
    isPartialFailure: boolean
}

const MAX_DISPLAY = 8

function classifyEventType(agent: string, eventType: string): DashboardEventType {
    const et = eventType.toLowerCase()
    const a = agent.toLowerCase()

    if (et.includes("voice") || a === "voice") return "voice"
    if (et.includes("browser") || a === "browser") return "browser"
    if (et.includes("computer") || a === "computer") return "computer"
    if (a === "research" || et.includes("research")) return "research"
    if (et.includes("governance") || a === "safety" || a === "guardrails") return "governance"
    if (a === "memory" || et.includes("memory")) return "system"
    if (a === "orchestrator" || et.includes("orchestration") || et.includes("orchestrator")) return "runtime"
    if (a === "planner" || a === "critic" || a === "optimizer" || a === "reflection") return "agent"
    if (et.includes("mission") || et.includes("goal") || et.includes("master")) return "mission"
    return "system"
}

function classifySeverity(status: string): DashboardEventSeverity {
    const s = status.toLowerCase()
    if (s === "completed" || s === "success" || s === "approved" || s === "passed") return "success"
    if (s === "failed" || s === "error" || s === "blocked" || s === "rejected" || s === "stopped") return "error"
    if (s === "warning" || s === "degraded") return "warning"
    return "info"
}

function makeTitle(eventType: string, message: string): string {
    const words = eventType.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
    if (message && message.length < 80) return message
    return words
}

function parseTimestamp(raw: unknown): Date | null {
    if (typeof raw === "string") {
        const d = new Date(raw)
        return Number.isFinite(d.getTime()) ? d : null
    }
    return null
}

function normalizeEvent(raw: Record<string, unknown>): DashboardEvent | null {
    const eventId = typeof raw["event_id"] === "string" ? raw["event_id"]
        : typeof raw["id"] === "string" ? raw["id"]
        : null
    if (!eventId) return null

    const agent = String(raw["agent"] ?? "system")
    const eventType = String(raw["event_type"] ?? raw["type"] ?? "unknown")
    const message = String(raw["message"] ?? "")
    const status = String(raw["status"] ?? "info")
    const timestamp = parseTimestamp(raw["timestamp"]) ?? new Date()

    return {
        id: eventId,
        timestamp,
        type: classifyEventType(agent, eventType),
        title: makeTitle(eventType, message),
        description: message,
        severity: classifySeverity(status),
        source: agent,
    }
}

export async function fetchDashboardEvents(): Promise<DashboardEvents> {
    try {
        const response = await runtimeService.getEvents()
        const rawList = response["events"]
        if (!Array.isArray(rawList)) {
            return { items: [], isPartialFailure: false }
        }

        const items: DashboardEvent[] = []

        for (const entry of rawList) {
            if (!entry || typeof entry !== "object") continue
            const event = normalizeEvent(entry as Record<string, unknown>)
            if (event) items.push(event)
        }

        items.sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())

        return {
            items: items.slice(0, MAX_DISPLAY),
            isPartialFailure: false,
        }
    } catch {
        return { items: [], isPartialFailure: true }
    }
}
