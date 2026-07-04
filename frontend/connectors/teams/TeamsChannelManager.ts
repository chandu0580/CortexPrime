import { TeamChannel, ChannelType } from "./types"
import { TeamsClient } from "./TeamsClient"

function mapApiChannel(api: Record<string, unknown>, teamId: string): TeamChannel {
  return {
    id: String(api.id),
    teamId,
    displayName: String(api.displayName),
    description: String(api.description ?? ""),
    type: (api.membershipType as string ?? "standard").toLowerCase() as ChannelType,
    members: [], pinnedMessages: [],
    archived: Boolean(api.isArchived),
    createdAt: String(api.createdDateTime ?? ""),
    updatedAt: "",
  }
}

export const TeamsChannelManager = {
  async createChannel(teamId: string, displayName: string, description: string = "", channelType: ChannelType = ChannelType.STANDARD): Promise<TeamChannel | null> {
    const body: Record<string, unknown> = { displayName, description }
    if (channelType === ChannelType.PRIVATE) body.membershipType = "private"
    const result = await TeamsClient.post<Record<string, unknown>>(`/teams/${teamId}/channels`, body)
    if (result.success && result.data) return mapApiChannel(result.data, teamId)
    return null
  },

  async archiveChannel(teamId: string, channelId: string): Promise<boolean> {
    const result = await TeamsClient.post(`/teams/${teamId}/channels/${channelId}/archive`)
    return result.success
  },

  async listChannels(teamId: string): Promise<TeamChannel[]> {
    const result = await TeamsClient.get<Record<string, unknown>>(`/teams/${teamId}/channels`)
    if (result.success && result.data?.value) {
      return (result.data.value as Record<string, unknown>[]).map((c) => mapApiChannel(c, teamId))
    }
    return []
  },

  async getChannel(teamId: string, channelId: string): Promise<TeamChannel | null> {
    const result = await TeamsClient.get<Record<string, unknown>>(`/teams/${teamId}/channels/${channelId}`)
    if (result.success && result.data) return mapApiChannel(result.data, teamId)
    return null
  },
}