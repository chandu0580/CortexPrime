import { NotionWorkspace, PageStatus } from "./types"
import { NotionClient } from "./NotionClient"

export const WorkspaceManager = {
  async getWorkspace(): Promise<NotionWorkspace | null> {
    const result = await NotionClient.get<Record<string, unknown>>("/users/me")
    if (result.success && result.data) {
      return { id: String(result.data.id), name: String((result.data as Record<string, unknown>).name ?? ""), domain: "", description: "", pages: [], databases: [], archived: false, createdAt: "", updatedAt: "" }
    }
    return null
  },

  async listWorkspaces(): Promise<NotionWorkspace[]> {
    const ws = await this.getWorkspace()
    return ws ? [ws] : []
  },
}