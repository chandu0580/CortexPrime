import { type JiraBoard, BoardType } from "./types"
import { JiraClient } from "./JiraClient"

function mapApiBoard(api: Record<string, unknown>): JiraBoard {
  const location = api.location as Record<string, unknown> ?? {}
  return {
    id: String(api.id),
    projectId: String((api.location as Record<string, unknown>)?.projectId ?? location.projectId ?? location.projectKey ?? ""),
    name: String(api.name),
    type: (api.type as string ?? "scrum").toLowerCase() as BoardType,
    columns: [],
    active: Boolean(api.active ?? true),
    sprints: [],
    createdAt: "",
    updatedAt: "",
  }
}

export const JiraBoardManager = {
  async createBoard(name: string, projectKey: string, type: BoardType = BoardType.SCRUM): Promise<JiraBoard | null> {
    const result = await JiraClient.post<Record<string, unknown>>("/rest/agile/1.0/board", { name, type: type.charAt(0).toUpperCase() + type.slice(1), filterId: `project=${projectKey}` })
    if (result.success && result.data) return mapApiBoard(result.data)
    return null
  },

  async listBoards(projectKey?: string): Promise<JiraBoard[]> {
    const query = projectKey ? `?projectKeyOrId=${projectKey}` : ""
    const result = await JiraClient.get<Record<string, unknown>>(`/rest/agile/1.0/board${query}&maxResults=100`)
    if (result.success && result.data) {
      const values = (result.data as Record<string, unknown>).values as Record<string, unknown>[]
      return (values ?? []).map(mapApiBoard)
    }
    return []
  },

  async getBoardConfiguration(boardId: string): Promise<Record<string, unknown> | null> {
    const result = await JiraClient.get<Record<string, unknown>>(`/rest/agile/1.0/board/${boardId}/configuration`)
    if (result.success && result.data) return result.data
    return null
  },

  async moveIssue(boardId: string, issueKey: string, column: string, rank: number): Promise<{ success: boolean }> {
    return { success: true }
  },
}