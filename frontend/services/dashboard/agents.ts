import { api } from "@/services/api"

export interface DashboardAgent {
    name: string
    displayName: string
    status: "running" | "idle" | "failed"
    agentType: string
    capabilities: string[]
    lastActive: string | null
    tasksCompleted: number
    errorCount: number
}

export interface DashboardAgents {
    items: DashboardAgent[]
    activeCount: number
    totalCount: number
    isPartialFailure: boolean
}

const DISPLAY_NAMES: Record<string, string> = {
    orchestrator: "Orchestrator",
    research: "Research Agent",
    planner: "Planner Agent",
    critic: "Critic Agent",
    optimizer: "Optimizer Agent",
    memory: "Memory Agent",
    reflection: "Reflection Agent",
    browser: "Browser Agent",
    voice: "Voice Agent",
    computer: "Computer Agent",
}

function mapStatus(raw: string): DashboardAgent["status"] {
    const s = raw.toLowerCase()
    if (s === "running" || s === "processing" || s === "active") return "running"
    if (s === "failed" || s === "error" || s === "stopped") return "failed"
    return "idle"
}

function normalizeAgent(name: string, raw: Record<string, unknown>): DashboardAgent {
    return {
        name,
        displayName: DISPLAY_NAMES[name] ?? name,
        status: mapStatus(String(raw["status"] ?? "idle")),
        agentType: String(raw["agent_type"] ?? "cognitive"),
        capabilities: Array.isArray(raw["capabilities"]) ? raw["capabilities"] as string[] : [],
        lastActive: typeof raw["last_active"] === "string" ? raw["last_active"] : null,
        tasksCompleted: typeof raw["task_count"] === "number" ? raw["task_count"] : 0,
        errorCount: typeof raw["error_count"] === "number" ? raw["error_count"] : 0,
    }
}

export async function fetchDashboardAgents(): Promise<DashboardAgents> {
    try {
        const response = await api.get<Record<string, unknown>>("/api/runtime/agents")
        const rawAgents = response["agents"]
        if (!rawAgents || typeof rawAgents !== "object") {
            return { items: [], activeCount: 0, totalCount: 0, isPartialFailure: false }
        }

        const items: DashboardAgent[] = []
        for (const [name, entry] of Object.entries(rawAgents)) {
            if (!entry || typeof entry !== "object") continue
            items.push(normalizeAgent(name, entry as Record<string, unknown>))
        }

        items.sort((a, b) => {
            const order = { running: 0, idle: 1, failed: 2 }
            const oa = order[a.status] ?? 1
            const ob = order[b.status] ?? 1
            if (oa !== ob) return oa - ob
            return a.displayName.localeCompare(b.displayName)
        })

        return {
            items,
            activeCount: items.filter((a) => a.status === "running").length,
            totalCount: items.length,
            isPartialFailure: false,
        }
    } catch {
        return { items: [], activeCount: 0, totalCount: 0, isPartialFailure: true }
    }
}
