import { type JiraWorkflow, type JiraTransition, WorkflowState } from "./types"
import { JiraClient } from "./JiraClient"

export const JiraWorkflowManager = {
  async listWorkflows(projectKey: string): Promise<JiraWorkflow[]> {
    const result = await JiraClient.get<Record<string, unknown>>(`/rest/api/3/workflow/search?queryString=&maxResults=50`)
    if (result.success && result.data) {
      const values = (result.data as Record<string, unknown>).values as Record<string, unknown>[]
      return (values ?? []).map((w) => ({
        id: String(w.id), projectId: projectKey, name: String(w.name), description: String(w.description ?? ""), states: [], transitions: [], state: WorkflowState.ACTIVE, createdAt: "", updatedAt: "",
      }))
    }
    return []
  },

  async retrieveTransitions(issueKey: string): Promise<JiraTransition[]> {
    const result = await JiraClient.get<Record<string, unknown>>(`/rest/api/3/issue/${issueKey}/transitions`)
    if (result.success && result.data) {
      const t = (result.data as Record<string, unknown>).transitions as Record<string, unknown>[]
      return (t ?? []).map((tr) => ({
        id: String(tr.id), workflowId: "", name: String(tr.name), fromStateId: "", toStateId: String((tr.to as Record<string, unknown>)?.id ?? ""), conditions: [],
      }))
    }
    return []
  },

  async executeTransition(issueKey: string, transitionId: string): Promise<boolean> {
    const result = await JiraClient.post(`/rest/api/3/issue/${issueKey}/transitions`, { transition: { id: transitionId } })
    return result.success
  },
}