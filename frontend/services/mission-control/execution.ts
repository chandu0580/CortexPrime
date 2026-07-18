import { api } from "@/services/api"
import { runtimeService } from "@/services/runtime"
import type { MissionSummaryItem } from "./missions"

export interface ExecutionResult {
  success: boolean
  execution_id?: string
  error?: string
}

export async function executeMission(objective: string, sessionId?: string): Promise<ExecutionResult> {
  try {
    const response = await api.post<{ accepted: boolean; execution_id?: string; message?: string }>("/execute", {
      objective,
      session_id: sessionId,
    })
    return {
      success: response.accepted ?? true,
      execution_id: response.execution_id,
    }
  } catch (err) {
    return { success: false, error: err instanceof Error ? err.message : "Failed to execute mission" }
  }
}

export async function getActiveMissions(): Promise<MissionSummaryItem[]> {
  try {
    const response = await runtimeService.getActiveMissions()
    const body = response as unknown as Record<string, unknown>
    const active = body["active_missions"]
    const missions: MissionSummaryItem[] = []
    if (active && typeof active === "object" && !Array.isArray(active)) {
      for (const [execId, entry] of Object.entries(active as Record<string, unknown>)) {
        if (!entry || typeof entry !== "object") continue
        const e = entry as Record<string, unknown>
        missions.push({
          execution_id: execId,
          goal: typeof e["goal"] === "string" ? e["goal"] : execId,
          status: "running",
          progress: null,
          startedAt: typeof e["started_at"] === "string" ? e["started_at"] : null,
          completedAt: null,
          assignedAgent: Array.isArray(e["agentsInvolved"]) && (e["agentsInvolved"] as string[]).length > 0
            ? (e["agentsInvolved"] as string[])[0]
            : undefined,
          agentsInvolved: Array.isArray(e["agentsInvolved"]) ? e["agentsInvolved"] as string[] : undefined,
        })
      }
    }
    return missions
  } catch {
    return []
  }
}

export async function getEvents(): Promise<{ event_id?: string; agent?: string; event_type?: string; status?: string; message?: string; timestamp?: string }[]> {
  try {
    const response = await runtimeService.getEvents()
    const body = response as unknown as Record<string, unknown>
    return Array.isArray(body["events"]) ? body["events"] as Record<string, unknown>[] : []
  } catch {
    return []
  }
}

export async function getRuntimeTelemetry(): Promise<Record<string, unknown> | null> {
  try {
    return await api.get<Record<string, unknown>>("/api/telemetry/runtime")
  } catch {
    return null
  }
}
