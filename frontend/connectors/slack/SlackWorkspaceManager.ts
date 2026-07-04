import { SlackWorkspace } from "./types"
import { SlackClient } from "./SlackClient"

function mapApiTeam(api: Record<string, unknown>): SlackWorkspace {
  const team = api.team as Record<string, unknown> ?? api
  return {
    id: String(team.id ?? api.id ?? ""),
    name: String(team.name ?? team.domain ?? ""),
    domain: String(team.domain ?? ""),
    description: String(team.description ?? ""),
    channels: [], users: [], userGroups: [], archived: false,
    createdAt: "", updatedAt: "",
  }
}

export const SlackWorkspaceManager = {
  async getWorkspaceInfo(): Promise<SlackWorkspace | null> {
    const result = await SlackClient.get<Record<string, unknown>>("/team.info")
    if (result.success && result.data) return mapApiTeam(result.data)
    return null
  },

  async listWorkspaces(): Promise<SlackWorkspace[]> {
    const info = await this.getWorkspaceInfo()
    return info ? [info] : []
  },

  async getWorkspace(id: string): Promise<SlackWorkspace | null> {
    const info = await this.getWorkspaceInfo()
    if (info && info.id === id) return info
    return null
  },
}