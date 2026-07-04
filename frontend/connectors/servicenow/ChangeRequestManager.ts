import { type ChangeRequest, ChangeState, PriorityLevel, ApprovalState } from "./types"
import { ServiceNowClient } from "./ServiceNowClient"

function mapApiChange(api: Record<string, unknown>): ChangeRequest {
  const state = String(api.state ?? "-1")
  let mappedState: ChangeState = ChangeState.NEW
  if (state === "-1") mappedState = ChangeState.NEW; else if (state === "0") mappedState = ChangeState.ASSESSING; else if (state === "1") mappedState = ChangeState.AUTHORIZING; else if (state === "2") mappedState = ChangeState.SCHEDULED; else if (state === "3") mappedState = ChangeState.IMPLEMENTING; else if (state === "4") mappedState = ChangeState.REVIEWING; else if (state === "5") mappedState = ChangeState.CLOSED; else mappedState = ChangeState.CANCELLED
  return {
    id: String(api.sys_id), instanceId: "", number: String(api.number), shortDescription: String(api.short_description ?? ""), description: String(api.description ?? ""),
    state: mappedState, priority: (api.priority as string ?? "3") === "1" ? PriorityLevel.CRITICAL : (api.priority as string ?? "3") === "2" ? PriorityLevel.HIGH : PriorityLevel.MEDIUM,
    riskLevel: (api.risk as string ?? "medium") as ChangeRequest["riskLevel"], category: String(api.category ?? ""),
    assignmentGroup: String(api.assignment_group ?? ""), assignedTo: (api.assigned_to as Record<string, unknown>)?.value as string ?? null,
    approval: (api.approval as string ?? "not_required") === "approved" ? ApprovalState.APPROVED : ApprovalState.PENDING,
    approver: null, plannedStartDate: api.start_date as string ?? null, plannedEndDate: api.end_date as string ?? null,
    openedAt: String(api.opened_at ?? api.sys_created_on ?? ""), implementedAt: api.implemented_at as string ?? null,
    closedAt: api.closed_at as string ?? null, createdAt: String(api.sys_created_on ?? ""), updatedAt: String(api.sys_updated_on ?? ""),
  }
}

export const ChangeRequestManager = {
  async createChange(shortDescription: string, description: string, priority: PriorityLevel = PriorityLevel.MEDIUM, riskLevel: "low" | "medium" | "high" | "extreme" = "medium", category: string = "", assignmentGroup: string = ""): Promise<ChangeRequest> {
    const body = { short_description: shortDescription, description, priority: priority === PriorityLevel.CRITICAL ? "1" : priority === PriorityLevel.HIGH ? "2" : "3", risk: riskLevel, category, assignment_group: assignmentGroup }
    const result = await ServiceNowClient.post<Record<string, unknown>>("/table/change_request", body)
    if (result.success && result.data?.result) return mapApiChange(result.data.result as Record<string, unknown>)
    const now = new Date().toISOString()
    return { id: "", instanceId: "", number: `CHG${now}`, shortDescription, description, state: ChangeState.NEW, priority, riskLevel, category, assignmentGroup, assignedTo: null, approval: ApprovalState.PENDING, approver: null, plannedStartDate: null, plannedEndDate: null, openedAt: now, implementedAt: null, closedAt: null, createdAt: now, updatedAt: now }
  },

  async approveChange(id: string, approver: string, state: ApprovalState): Promise<ChangeRequest | null> {
    const body: Record<string, unknown> = { approval: state === ApprovalState.APPROVED ? "approved" : "rejected", assigned_to: approver }
    if (state === ApprovalState.APPROVED) body.state = "1"
    const result = await ServiceNowClient.patch<Record<string, unknown>>(`/table/change_request/${id}`, body)
    if (result.success && result.data?.result) return mapApiChange(result.data.result as Record<string, unknown>)
    return null
  },

  async implementChange(id: string): Promise<ChangeRequest | null> {
    const result = await ServiceNowClient.patch<Record<string, unknown>>(`/table/change_request/${id}`, { state: "3" })
    if (result.success && result.data?.result) return mapApiChange(result.data.result as Record<string, unknown>)
    return null
  },

  async closeChange(id: string): Promise<ChangeRequest | null> {
    const result = await ServiceNowClient.patch<Record<string, unknown>>(`/table/change_request/${id}`, { state: "5" })
    if (result.success && result.data?.result) return mapApiChange(result.data.result as Record<string, unknown>)
    return null
  },

  async listChanges(): Promise<ChangeRequest[]> {
    const result = await ServiceNowClient.get<Record<string, unknown>>("/table/change_request?sysparm_limit=100")
    if (result.success && result.data?.result) return (result.data.result as Record<string, unknown>[]).map(mapApiChange)
    return []
  },
}