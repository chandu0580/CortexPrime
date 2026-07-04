import { JiraSprint, SprintState } from "./types"
import { JiraClient } from "./JiraClient"

function mapApiSprint(api: Record<string, unknown>, boardId: string): JiraSprint {
  return {
    id: String(api.id),
    projectId: String(api.originBoardId ?? api.projectId ?? ""),
    boardId,
    name: String(api.name),
    goal: String(api.goal ?? ""),
    state: (api.state as string ?? "future").toLowerCase() as SprintState,
    startDate: api.startDate as string ?? null,
    endDate: api.endDate as string ?? null,
    completedDate: api.completeDate as string ?? api.completedDate as string ?? null,
    issues: [],
    createdAt: api.createdDate as string ?? new Date().toISOString(),
  }
}

export const JiraSprintManager = {
  async createSprint(boardId: string, name: string, goal: string = ""): Promise<JiraSprint> {
    const result = await JiraClient.post<Record<string, unknown>>("/rest/agile/1.0/sprint", { name, goal, originBoardId: parseInt(boardId, 10) })
    if (result.success && result.data) return mapApiSprint(result.data, boardId)
    const now = new Date().toISOString()
    return { id: "", projectId: "", boardId, name, goal, state: "future" as SprintState, startDate: null, endDate: null, completedDate: null, issues: [], createdAt: now }
  },

  async startSprint(sprintId: string): Promise<JiraSprint | null> {
    const result = await JiraClient.post<Record<string, unknown>>(`/rest/agile/1.0/sprint/${sprintId}`, { state: "active" })
    if (result.success && result.data) return mapApiSprint(result.data, String(result.data.originBoardId ?? ""))
    return null
  },

  async completeSprint(sprintId: string): Promise<JiraSprint | null> {
    const result = await JiraClient.post<Record<string, unknown>>(`/rest/agile/1.0/sprint/${sprintId}`, { state: "closed" })
    if (result.success && result.data) return mapApiSprint(result.data, String(result.data.originBoardId ?? ""))
    return null
  },

  async moveIssueToSprint(sprintId: string, issueKeys: string[]): Promise<boolean> {
    const result = await JiraClient.post(`/rest/agile/1.0/sprint/${sprintId}/issue`, { issues: issueKeys })
    return result.success
  },

  async listSprints(boardId: string): Promise<JiraSprint[]> {
    const result = await JiraClient.get<Record<string, unknown>>(`/rest/agile/1.0/board/${boardId}/sprint?maxResults=100`)
    if (result.success && result.data) {
      const values = (result.data as Record<string, unknown>).values as Record<string, unknown>[]
      return (values ?? []).map((s) => mapApiSprint(s, boardId))
    }
    return []
  },

  async getSprint(sprintId: string): Promise<JiraSprint | null> {
    const result = await JiraClient.get<Record<string, unknown>>(`/rest/agile/1.0/sprint/${sprintId}`)
    if (result.success && result.data) return mapApiSprint(result.data, String(result.data.originBoardId ?? ""))
    return null
  },
}