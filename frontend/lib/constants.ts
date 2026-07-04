// ==========================================
// CONSTANTS
// ==========================================

const DEV_API_BASE_URL = "http://localhost:8000"
const DEV_WS_URL = "ws://localhost:8000/ws"

function stripTrailingSlash(value: string): string {
    return value.endsWith("/") ? value.slice(0, -1) : value
}

export function getApiBaseUrl(): string {
    const configured = stripTrailingSlash(process.env.NEXT_PUBLIC_API_URL ?? "")

    if (typeof window !== "undefined") {
        const origin = stripTrailingSlash(window.location.origin)

        if (window.location.protocol === "https:" && (!configured || configured === origin)) {
            return ""
        }
    }

    return configured || DEV_API_BASE_URL
}

export function apiUrl(path: string): string {
    const normalizedPath = path.startsWith("/") ? path : `/${path}`
    const base = getApiBaseUrl()
    return base ? `${base}${normalizedPath}` : normalizedPath
}

export function getWsUrl(path = "/ws"): string {
    const normalizedPath = path.startsWith("/") ? path : `/${path}`
    const configured = process.env.NEXT_PUBLIC_WS_URL?.trim()

    if (typeof window !== "undefined") {
        const protocol = window.location.protocol === "https:" ? "wss" : "ws"
        const sameOrigin = `${protocol}://${window.location.host}`

        if (!configured) {
            return `${sameOrigin}${normalizedPath}`
        }

        try {
            const parsed = new URL(configured)
            const sameHost = parsed.host === window.location.host
            const sameProtocol =
                (parsed.protocol === "wss:" && protocol === "wss") ||
                (parsed.protocol === "ws:" && protocol === "ws")

            if (sameHost && sameProtocol) {
                return `${sameOrigin}${parsed.pathname}${parsed.search}`
            }
        } catch {
            if (configured.startsWith("/")) {
                return `${sameOrigin}${configured}`
            }
        }

        return configured
    }

    return configured || DEV_WS_URL
}

export const API_BASE_URL = getApiBaseUrl()
export const WS_URL = getWsUrl()

export const AGENT_COLORS: Record<string, string> = {
    orchestrator: "#82c0a4",
    planner:      "#4a8c70",
    research:     "#6aaf8a",
    critic:       "#f9a825",
    optimizer:    "#96cead",
    memory:       "#737373",
    reflection:   "#82c0a4",
    system:       "#737373",
}

export const STATUS_COLORS = {
    active:     "#82c0a4",
    idle:       "#737373",
    processing: "#4a8c70",
    error:      "#ef4444",
    done:       "#96cead",
    degraded:   "#f9a825",
}

export const AGENT_LABELS: Record<string, string> = {
    orchestrator: "Orchestrator",
    planner:      "Planner",
    research:     "Research",
    critic:       "Critic",
    optimizer:    "Optimizer",
    memory:       "Memory",
    system:       "System",
}

export const POLL_INTERVAL_MS = 3000
export const WS_RECONNECT_INTERVAL_MS = 3000
export const WS_MAX_RECONNECT_ATTEMPTS = 10
export const MAX_EVENTS_IN_FEED = 100
export const MAX_CHAT_MESSAGES = 200
