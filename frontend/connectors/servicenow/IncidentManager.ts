import { type Incident, IncidentState, PriorityLevel } from "./types"
import { ServiceNowClient } from "./ServiceNowClient"

function mapApiIncident(api: Record<string, unknown>): Incident {
  return {
    id: String(api.sys_id), instanceId: "", number: String(api.number),
    shortDescription: String(api.short_description ?? ""), description: String(api.description ?? ""),
    state: (api.state as string ?? "1") === "1" ? IncidentState.NEW : (api.state as string ?? "2") === "2" ? IncidentState.IN_PROGRESS : IncidentState.CLOSED,
    priority: (api.priority as string ?? "3") === "1" ? PriorityLevel.CRITICAL : (api.priority as string ?? "3") === "2" ? PriorityLevel.HIGH : PriorityLevel.MEDIUM,
    assignmentGroup: String(api.assignment_group ?? ""), assignedTo: (api.assigned_to as Record<string, unknown>)?.value as string ?? null,
    callerId: String(api.caller_id ?? ""), category: String(api.category ?? ""),
    impact: String(api.impact ?? "3"), urgency: String(api.urgency ?? "3"),
    resolutionCode: api.close_notes as string ?? null, resolutionNotes: api.close_notes as string ?? null,
    openedAt: String(api.opened_at ?? api.sys_created_on ?? ""),
    resolvedAt: api.resolved_at as string ?? null, closedAt: api.closed_at as string ?? null,
    createdAt: String(api.sys_created_on ?? ""), updatedAt: String(api.sys_updated_on ?? ""),
  }
}

export const IncidentManager = {
  async createIncident(shortDescription: string, description: string, callerId: string, priority: PriorityLevel = PriorityLevel.MEDIUM, category: string = "", assignmentGroup: string = ""): Promise<Incident> {
    const body = { short_description: shortDescription, description, caller_id: callerId, priority: priority === PriorityLevel.CRITICAL ? "1" : priority === PriorityLevel.HIGH ? "2" : "3", category, assignment_group: assignmentGroup }
    const result = await ServiceNowClient.post<Record<string, unknown>>("/table/incident", body)
    if (result.success && result.data?.result) return mapApiIncident(result.data.result as Record<string, unknown>)
    const now = new Date().toISOString()
    return { id: "", instanceId: "", number: `INC${now}`, shortDescription, description, state: IncidentState.NEW, priority, assignmentGroup, assignedTo: null, callerId, category, impact: "3", urgency: "3", resolutionCode: null, resolutionNotes: null, openedAt: now, resolvedAt: null, closedAt: null, createdAt: now, updatedAt: now }
  },

  async updateIncident(id: string, updates: Record<string, unknown>): Promise<Incident | null> {
    const result = await ServiceNowClient.patch<Record<string, unknown>>(`/table/incident/${id}`, updates)
    if (result.success && result.data?.result) return mapApiIncident(result.data.result as Record<string, unknown>)
    return null
  },

  async assignIncident(id: string, assignedTo: string, assignmentGroup: string): Promise<Incident | null> {
    return this.updateIncident(id, { assigned_to: assignedTo, assignment_group: assignmentGroup, state: "2" })
  },

  async resolveIncident(id: string, resolutionCode: string, resolutionNotes: string): Promise<Incident | null> {
    return this.updateIncident(id, { state: "6", close_code: resolutionCode, close_notes: resolutionNotes, resolved_at: new Date().toISOString() })
  },

  async closeIncident(id: string): Promise<Incident | null> {
    return this.updateIncident(id, { state: "7", closed_at: new Date().toISOString() })
  },

  async listIncidents(): Promise<Incident[]> {
    const result = await ServiceNowClient.get<Record<string, unknown>>("/table/incident?sysparm_limit=100")
    if (result.success && result.data?.result) return (result.data.result as Record<string, unknown>[]).map(mapApiIncident)
    return []
  },
}