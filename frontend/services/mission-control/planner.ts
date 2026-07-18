import { runtimeService } from "@/services/runtime"
import { api } from "@/services/api"

export interface PlanInput {
  objective: string
  session_id?: string
  workspace_id?: string
}

export interface PlanResult {
  accepted: boolean
  execution_id: string | null
  message: string
}

export interface ExecutionPlan {
  stages: string[]
  agents: string[]
  currentStage: string
  status: string
  execution_id: string
}

export async function planMission(input: PlanInput): Promise<PlanResult> {
  try {
    const response = await api.post<{ accepted: boolean; execution_id?: string; message: string }>("/api/orchestrator/execute", {
      objective: input.objective,
      session_id: input.session_id,
    })
    return {
      accepted: response.accepted ?? true,
      execution_id: response.execution_id ?? null,
      message: response.message ?? "Mission accepted",
    }
  } catch {
    return { accepted: false, execution_id: null, message: "Failed to submit mission" }
  }
}

export async function getPlan(executionId: string): Promise<ExecutionPlan | null> {
  try {
    const response = await runtimeService.getActiveMissions()
    const body = response as unknown as Record<string, unknown>
    const active = body["active_missions"] as Record<string, unknown> | undefined
    if (active && typeof active === "object") {
      const entry = active[executionId] as Record<string, unknown> | undefined
      if (entry) {
        const stages = entry["stages"] ?? entry["execution_stages"] ?? []
        const agents = entry["agentsInvolved"] ?? []
        return {
          stages: Array.isArray(stages) ? stages as string[] : [],
          agents: Array.isArray(agents) ? agents as string[] : [],
          currentStage: String(entry["stage"] ?? entry["currentStage"] ?? ""),
          status: String(entry["status"] ?? "unknown"),
          execution_id: executionId,
        }
      }
    }
    return null
  } catch {
    return null
  }
}
