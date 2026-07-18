import { WorkItemState, type AzureBoard, type AzureWorkItem } from "./types"
import { AzureDevOpsClient } from "./AzureDevOpsClient"

function mapApiWorkItem(api: Record<string, unknown>, projectId: string): AzureWorkItem {
  const fields = api.fields as Record<string, unknown> ?? {}
  return {
    id: String(api.id), boardId: "", projectId,
    title: String(fields["System.Title"] ?? ""), description: String(fields["System.Description"] ?? ""),
    state: (fields["System.State"] as string ?? "New").toLowerCase().replace(/ /g, "_") as WorkItemState,
    assignedTo: (fields["System.AssignedTo"] as Record<string, unknown>)?.displayName as string ?? null,
    workItemType: (fields["System.WorkItemType"] as string ?? "Task").toLowerCase() as AzureWorkItem["workItemType"],
    priority: Number(fields["Microsoft.VSTS.Common.Priority"] ?? 2),
    storyPoints: Number(fields["Microsoft.VSTS.Scheduling.StoryPoints"] ?? 0),
    tags: ((fields["System.Tags"] as string) ?? "").split("; ").filter(Boolean),
    createdAt: String(fields["System.CreatedDate"] ?? ""),
    updatedAt: String(fields["System.ChangedDate"] ?? ""),
    closedAt: fields["Microsoft.VSTS.Common.ClosedDate"] as string ?? null,
  }
}

export const AzureBoardManager = {
  async createBoard(projectId: string, name: string, description: string = "", columns: string[] = ["New", "Active", "Resolved", "Closed"]): Promise<AzureBoard> {
    const body = { name, description, filter: "", columns: columns.map((c) => ({ name: c, itemLimit: 0 })) }
    const result = await AzureDevOpsClient.post<Record<string, unknown>>(`/${projectId}/_apis/work/boards`, body)
    const now = new Date().toISOString()
    if (result.success && result.data) {
      return { id: String(result.data.id), projectId, name: String(result.data.name), description: String(result.data.description ?? ""), columns: (result.data.columns as Record<string, unknown>[] ?? []).map((c) => String(c.name ?? c)), workItems: [], createdAt: String(result.data.createdDate ?? now), updatedAt: String(result.data.updatedDate ?? now) }
    }
    return { id: name, projectId, name, description, columns, workItems: [], createdAt: now, updatedAt: now }
  },

  async createWorkItem(projectId: string, title: string, description: string, workItemType: AzureWorkItem["workItemType"], priority: number = 2, storyPoints: number = 0): Promise<AzureWorkItem | null> {
    const body = [{ op: "add", path: "/fields/System.Title", value: title }, { op: "add", path: "/fields/System.Description", value: description }, { op: "add", path: "/fields/Microsoft.VSTS.Common.Priority", value: priority }]
    if (storyPoints > 0) body.push({ op: "add", path: "/fields/Microsoft.VSTS.Scheduling.StoryPoints", value: storyPoints })
    const type = workItemType.charAt(0).toUpperCase() + workItemType.slice(1)
    const result = await AzureDevOpsClient.post<Record<string, unknown>>(`/${projectId}/_apis/wit/workitems/$${type}`, body)
    if (result.success && result.data) return mapApiWorkItem(result.data, projectId)
    return null
  },

  async assignWorkItem(id: string, projectId: string, assignedTo: string): Promise<AzureWorkItem | null> {
    const body = [{ op: "add", path: "/fields/System.AssignedTo", value: assignedTo }]
    const result = await AzureDevOpsClient.patch<Record<string, unknown>>(`/${projectId}/_apis/wit/workitems/${id}`, body)
    if (result.success && result.data) return mapApiWorkItem(result.data, projectId)
    return null
  },

  async transitionWorkItem(id: string, projectId: string, state: WorkItemState): Promise<AzureWorkItem | null> {
    const stateName = state.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())
    const body = [{ op: "add", path: "/fields/System.State", value: stateName }]
    const result = await AzureDevOpsClient.patch<Record<string, unknown>>(`/${projectId}/_apis/wit/workitems/${id}`, body)
    if (result.success && result.data) return mapApiWorkItem(result.data, projectId)
    return null
  },

  async closeWorkItem(id: string, projectId: string): Promise<AzureWorkItem | null> {
    return this.transitionWorkItem(id, projectId, WorkItemState.CLOSED)
  },

  async queryWorkItems(projectId: string, wiql: string): Promise<AzureWorkItem[]> {
    const result = await AzureDevOpsClient.post<Record<string, unknown>>(`/${projectId}/_apis/wit/wiql`, { query: wiql })
    if (result.success && result.data?.workItems) {
      const items = result.data.workItems as Record<string, unknown>[]
      const ids = items.map((i) => String(i.id)).join(",")
      if (!ids) return []
      const detailResult = await AzureDevOpsClient.get<Record<string, unknown>>(`/_apis/wit/workitems?ids=${ids}&$expand=all`)
      if (detailResult.success && detailResult.data?.value) return (detailResult.data.value as Record<string, unknown>[]).map((w) => mapApiWorkItem(w, projectId))
    }
    return []
  },

  async listBoards(projectId: string): Promise<AzureBoard[]> {
    const result = await AzureDevOpsClient.get<Record<string, unknown>>(`/${projectId}/_apis/work/boards?$top=100`)
    if (result.success && result.data?.value) {
      return (result.data.value as Record<string, unknown>[]).map((b) => ({
        id: String(b.id), projectId, name: String(b.name), description: String(b.description ?? ""),
        columns: (b.columns as Record<string, unknown>[] ?? []).map((c) => String(c.name ?? c)),
        workItems: [], createdAt: "", updatedAt: "",
      }))
    }
    return []
  },

  async getBoard(id: string): Promise<AzureBoard | null> {
    const projectId = id.split("/")[0] ?? ""
    const boardId = id.split("/")[1] ?? id
    const result = await AzureDevOpsClient.get<Record<string, unknown>>(`/${projectId}/_apis/work/boards/${boardId}`)
    if (result.success && result.data) {
      return {
        id: String(result.data.id), projectId, name: String(result.data.name), description: String(result.data.description ?? ""),
        columns: (result.data.columns as Record<string, unknown>[] ?? []).map((c) => String(c.name ?? c)),
        workItems: [], createdAt: "", updatedAt: "",
      }
    }
    return null
  },

  async getWorkItem(id: string): Promise<AzureWorkItem | null> {
    const result = await AzureDevOpsClient.get<Record<string, unknown>>(`/_apis/wit/workitems/${id}?$expand=all`)
    if (result.success && result.data) return mapApiWorkItem(result.data, "")
    return null
  },

  async listWorkItems(boardId: string): Promise<AzureWorkItem[]> {
    const ids = boardId.split("/")
    const projectId = ids[0] ?? ""
    const boardName = ids[1] ?? boardId
    const wiql = `SELECT [System.Id] FROM WorkItems WHERE [System.BoardName] = '${boardName}'`
    return this.queryWorkItems(projectId, wiql)
  },
}