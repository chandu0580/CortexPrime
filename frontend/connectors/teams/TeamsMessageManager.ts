import { TeamMessage, TeamMention, TeamAttachment } from "./types"
import { TeamsClient } from "./TeamsClient"

function mapApiMessage(api: Record<string, unknown>, channelId: string): TeamMessage {
  const from = api.from as Record<string, unknown> ?? {}
  const user = from.user as Record<string, unknown> ?? {}
  return {
    id: String(api.id),
    channelId,
    userId: String(user.id ?? ""),
    displayName: String(user.displayName ?? ""),
    subject: String(api.subject ?? ""),
    body: String((api.body as Record<string, unknown>)?.content ?? ""),
    messageType: String(api.messageType ?? "message") as TeamMessage["messageType"],
    parentMessageId: (api as Record<string, unknown>).replyToId as string ?? null,
    mentions: [], attachments: [],
    pinned: false, edited: false, editedAt: null,
    createdAt: String(api.createdDateTime ?? api.created_at ?? new Date().toISOString()),
    updatedAt: String(api.lastModifiedDateTime ?? api.updatedAt ?? new Date().toISOString()),
  }
}

export const TeamsMessageManager = {
  async createMessage(teamId: string, channelId: string, body: string, subject: string = ""): Promise<TeamMessage> {
    const bodyContent = { body: { contentType: "html", content: body }, subject }
    const result = await TeamsClient.post<Record<string, unknown>>(`/teams/${teamId}/channels/${channelId}/messages`, bodyContent)
    if (result.success && result.data) return mapApiMessage(result.data, channelId)
    const now = new Date().toISOString()
    return { id: "", channelId, userId: "", displayName: "", subject, body, messageType: "message", parentMessageId: null, mentions: [], attachments: [], pinned: false, edited: false, editedAt: null, createdAt: now, updatedAt: now }
  },

  async editMessage(teamId: string, channelId: string, messageId: string, body: string): Promise<TeamMessage | null> {
    const result = await TeamsClient.patch<Record<string, unknown>>(`/teams/${teamId}/channels/${channelId}/messages/${messageId}`, { body: { contentType: "html", content: body } })
    if (result.success && result.data) return mapApiMessage(result.data, channelId)
    return null
  },

  async deleteMessage(teamId: string, channelId: string, messageId: string): Promise<boolean> {
    const result = await TeamsClient.delete(`/teams/${teamId}/channels/${channelId}/messages/${messageId}`)
    return result.success
  },

  async listMessages(teamId: string, channelId: string): Promise<TeamMessage[]> {
    const result = await TeamsClient.get<Record<string, unknown>>(`/teams/${teamId}/channels/${channelId}/messages?$top=100`)
    if (result.success && result.data?.value) {
      return (result.data.value as Record<string, unknown>[]).map((m) => mapApiMessage(m, channelId))
    }
    return []
  },

  async retrieveMessage(teamId: string, channelId: string, messageId: string): Promise<TeamMessage | null> {
    const result = await TeamsClient.get<Record<string, unknown>>(`/teams/${teamId}/channels/${channelId}/messages/${messageId}`)
    if (result.success && result.data) return mapApiMessage(result.data, channelId)
    return null
  },
}