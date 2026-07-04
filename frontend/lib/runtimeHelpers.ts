import type { AgentNode } from "@/types/cognition"
import { AGENT_COLORS, STATUS_COLORS } from "./constants"

// ==========================================
// RUNTIME HELPERS
// ==========================================

export function getAgentColor(agentId: string): string {
    return AGENT_COLORS[agentId.toLowerCase()] ?? "#737373"
}

export function getStatusColor(status: string): string {
    return STATUS_COLORS[status as keyof typeof STATUS_COLORS] ?? "#737373"
}

export function formatLatency(ms: number): string {
    if (ms < 1000) return `${ms}ms`
    return `${(ms / 1000).toFixed(1)}s`
}

export function formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / 1_048_576).toFixed(1)} MB`
}

export function buildDefaultAgentNodes(): AgentNode[] {
    return [
        { id: "orchestrator", label: "Orchestrator", status: "idle", type: "orchestrator", x: 300, y: 50 },
        { id: "planner",      label: "Planner",      status: "idle", type: "planner",      x: 100, y: 200 },
        { id: "research",     label: "Research",     status: "idle", type: "research",     x: 300, y: 200 },
        { id: "critic",       label: "Critic",       status: "idle", type: "critic",       x: 500, y: 200 },
        { id: "optimizer",    label: "Optimizer",    status: "idle", type: "optimizer",    x: 200, y: 350 },
        { id: "memory",       label: "Memory",       status: "idle", type: "memory",       x: 400, y: 350 },
    ]
}

export function truncateText(text: string, max = 80): string {
    return text.length > max ? `${text.slice(0, max)}…` : text
}
