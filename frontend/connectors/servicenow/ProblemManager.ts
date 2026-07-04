import { type Problem, PriorityLevel } from "./types"
import { ServiceNowClient } from "./ServiceNowClient"

function mapApiProblem(api: Record<string, unknown>): Problem {
  const state = String(api.state ?? "1")
  let mappedState: Problem["state"] = "under_investigation"
  if (state === "1") mappedState = "under_investigation"; else if (state === "2") mappedState = "root_cause_identified"; else if (state === "3") mappedState = "known_error"; else if (state === "4") mappedState = "resolved"; else mappedState = "closed"
  return {
    id: String(api.sys_id), instanceId: "", number: String(api.number), shortDescription: String(api.short_description ?? ""), description: String(api.description ?? ""),
    state: mappedState, priority: (api.priority as string ?? "3") === "1" ? PriorityLevel.CRITICAL : (api.priority as string ?? "3") === "2" ? PriorityLevel.HIGH : PriorityLevel.MEDIUM,
    assignmentGroup: String(api.assignment_group ?? ""), assignedTo: (api.assigned_to as Record<string, unknown>)?.value as string ?? null,
    workaround: api.workaround as string ?? null, knownError: state === "3", relatedIncidents: [],
    openedAt: String(api.opened_at ?? api.sys_created_on ?? ""), resolvedAt: api.resolved_at as string ?? null,
    closedAt: api.closed_at as string ?? null, createdAt: String(api.sys_created_on ?? ""), updatedAt: String(api.sys_updated_on ?? ""),
  }
}

export const ProblemManager = {
  async createProblem(shortDescription: string, description: string, priority: PriorityLevel = PriorityLevel.MEDIUM, assignmentGroup: string = ""): Promise<Problem> {
    const body = { short_description: shortDescription, description, priority: priority === PriorityLevel.CRITICAL ? "1" : priority === PriorityLevel.HIGH ? "2" : "3", assignment_group: assignmentGroup }
    const result = await ServiceNowClient.post<Record<string, unknown>>("/table/problem", body)
    if (result.success && result.data?.result) return mapApiProblem(result.data.result as Record<string, unknown>)
    const now = new Date().toISOString()
    return { id: "", instanceId: "", number: `PRB${now}`, shortDescription, description, state: "under_investigation", priority, assignmentGroup, assignedTo: null, workaround: null, knownError: false, relatedIncidents: [], openedAt: now, resolvedAt: null, closedAt: null, createdAt: now, updatedAt: now }
  },

  async updateProblem(id: string, updates: Record<string, unknown>): Promise<Problem | null> {
    const result = await ServiceNowClient.patch<Record<string, unknown>>(`/table/problem/${id}`, updates)
    if (result.success && result.data?.result) return mapApiProblem(result.data.result as Record<string, unknown>)
    return null
  },

  async resolveProblem(id: string, workaround: string, knownError: boolean): Promise<Problem | null> {
    return this.updateProblem(id, { workaround, state: knownError ? "3" : "4", resolved_at: new Date().toISOString() })
  },

  async closeProblem(id: string): Promise<Problem | null> {
    return this.updateProblem(id, { state: "5", closed_at: new Date().toISOString() })
  },

  async listProblems(): Promise<Problem[]> {
    const result = await ServiceNowClient.get<Record<string, unknown>>("/table/problem?sysparm_limit=100")
    if (result.success && result.data?.result) return (result.data.result as Record<string, unknown>[]).map(mapApiProblem)
    return []
  },
}