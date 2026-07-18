import { runtimeService } from "@/services/runtime"
import { api } from "@/services/api"

export interface MissionsFilter {
  status?: string
  priority?: string
  search?: string
  page?: number
  limit?: number
}

export interface MissionSummaryItem {
  execution_id: string
  goal?: string
  status: "queued" | "running" | "completed" | "failed"
  progress: number | null
  startedAt: string | null
  completedAt: string | null
  assignedAgent?: string
  agentsInvolved?: string[]
}

export interface MissionTimelineEvent {
  event_id: string
  sequence: number
  event_type: string
  agent: string
  status: string
  message: string
  timestamp: string | null
  latency_ms?: number
  offset_ms?: number
  phase?: string
}

function normalizeStatus(raw: unknown): MissionSummaryItem["status"] {
  if (typeof raw !== "string") return "queued"
  const s = raw.toLowerCase()
  if (s === "active" || s === "running" || s === "in_progress") return "running"
  if (s === "completed" || s === "complete") return "completed"
  if (s === "failed" || s === "error" || s === "cancelled") return "failed"
  return "queued"
}

function pickFirstAgent(raw: unknown): string | undefined {
  if (Array.isArray(raw) && raw.length > 0 && typeof raw[0] === "string") return raw[0]
  return undefined
}

export async function getMissions(): Promise<MissionSummaryItem[]> {
  const results = await Promise.allSettled([
    runtimeService.getActiveMissions(),
    runtimeService.getCompletedMissions(),
  ])

  const items: MissionSummaryItem[] = []

  for (const result of results) {
    if (result.status !== "fulfilled") continue
    const body = result.value as Record<string, unknown>

    const activeEntries = body["active_missions"]
    if (activeEntries && typeof activeEntries === "object" && !Array.isArray(activeEntries)) {
      for (const [execId, entry] of Object.entries(activeEntries as Record<string, unknown>)) {
        if (!entry || typeof entry !== "object") continue
        const e = entry as Record<string, unknown>
        items.push({
          execution_id: execId,
          goal: typeof e["goal"] === "string" ? e["goal"] : execId,
          status: normalizeStatus(e["status"]),
          progress: null,
          startedAt: typeof e["started_at"] === "string" ? e["started_at"] : null,
          completedAt: null,
          assignedAgent: pickFirstAgent(e["agentsInvolved"]),
          agentsInvolved: Array.isArray(e["agentsInvolved"]) ? e["agentsInvolved"] as string[] : undefined,
        })
      }
    }

    const completedList = body["completed_missions"]
    if (Array.isArray(completedList)) {
      for (const entry of completedList) {
        if (!entry || typeof entry !== "object") continue
        const e = entry as Record<string, unknown>
        const execId = typeof e["execution_id"] === "string" ? e["execution_id"]
          : typeof e["id"] === "string" ? e["id"]
          : `completed-${Math.random().toString(36).slice(2, 8)}`
        items.push({
          execution_id: execId,
          goal: typeof e["goal"] === "string" ? e["goal"] : execId,
          status: "completed",
          progress: 100,
          startedAt: typeof e["started_at"] === "string" ? e["started_at"] : null,
          completedAt: typeof e["completed_at"] === "string" ? e["completed_at"] : null,
          assignedAgent: pickFirstAgent(e["agentsInvolved"]),
          agentsInvolved: Array.isArray(e["agentsInvolved"]) ? e["agentsInvolved"] as string[] : undefined,
        })
      }
    }
  }

  items.sort((a, b) => {
    const ta = a.startedAt ? new Date(a.startedAt).getTime() : 0
    const tb = b.startedAt ? new Date(b.startedAt).getTime() : 0
    return tb - ta
  })

  return items
}

export async function getMission(executionId: string): Promise<MissionSummaryItem | null> {
  const missions = await getMissions()
  return missions.find((m) => m.execution_id === executionId) ?? null
}

export async function getMissionReplay(executionId: string): Promise<MissionTimelineEvent[]> {
  try {
    const response = await api.get<{ events: MissionTimelineEvent[] }>(`/api/mission-replay/${executionId}`)
    return response.events ?? []
  } catch {
    return []
  }
}

export async function getMissionReplayTimeline(executionId: string): Promise<MissionTimelineEvent[]> {
  try {
    const response = await api.get<MissionTimelineEvent[]>(`/api/mission-replay/${executionId}/timeline`)
    return Array.isArray(response) ? response : []
  } catch {
    return []
  }
}
