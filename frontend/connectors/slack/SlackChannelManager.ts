import { type SlackChannel, ChannelType } from "./types"
import { SlackClient } from "./SlackClient"

function mapApiChannel(api: Record<string, unknown>, workspaceId: string): SlackChannel {
  return {
    id: String(api.id),
    workspaceId,
    name: String(api.name),
    topic: String((api.topic as Record<string, unknown>)?.value ?? ""),
    purpose: String((api.purpose as Record<string, unknown>)?.value ?? ""),
    type: api.is_mpim ? ChannelType.MULTIPARTY_DM : api.is_im ? ChannelType.DIRECT_MESSAGE : api.is_private ? ChannelType.PRIVATE : ChannelType.PUBLIC,
    members: (api.members as string[]) ?? [],
    pinnedMessages: [],
    archived: Boolean(api.is_archived),
    createdAt: String(api.created),
    updatedAt: "",
  }
}

export const SlackChannelManager = {
  async createChannel(name: string, isPrivate: boolean = false): Promise<SlackChannel | null> {
    const result = await SlackClient.post<Record<string, unknown>>("/conversations.create", { name, is_private: isPrivate })
    if (result.success && result.data?.channel) return mapApiChannel(result.data.channel as Record<string, unknown>, "")
    return null
  },

  async archiveChannel(channelId: string): Promise<boolean> {
    const result = await SlackClient.post("/conversations.archive", { channel: channelId })
    return result.success
  },

  async inviteMember(channelId: string, userId: string): Promise<boolean> {
    const result = await SlackClient.post("/conversations.invite", { channel: channelId, users: userId })
    return result.success
  },

  async listChannels(): Promise<SlackChannel[]> {
    const result = await SlackClient.post<Record<string, unknown>>("/conversations.list", { exclude_archived: false, limit: 200, types: "public_channel,private_channel" })
    if (result.success && result.data?.channels) {
      return (result.data.channels as Record<string, unknown>[]).map((c) => mapApiChannel(c, ""))
    }
    return []
  },

  async getChannel(channelId: string): Promise<SlackChannel | null> {
    const result = await SlackClient.post<Record<string, unknown>>("/conversations.info", { channel: channelId })
    if (result.success && result.data?.channel) return mapApiChannel(result.data.channel as Record<string, unknown>, "")
    return null
  },
}