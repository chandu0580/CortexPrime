import { SlackMessage, SlackMention, SlackAttachment } from "./types"
import { MessageType } from "./types"
import { SlackClient } from "./SlackClient"

function mapApiMessage(api: Record<string, unknown>, channelId: string): SlackMessage {
  return {
    id: String(api.ts),
    channelId,
    userId: String(api.user ?? api.bot_id ?? ""),
    text: String(api.text ?? ""),
    type: api.thread_ts ? MessageType.THREAD_REPLY : MessageType.STANDARD,
    threadId: api.thread_ts as string ?? null,
    mentions: [],
    attachments: (api.attachments as Record<string, unknown>[] ?? []).map((a) => ({ id: String(a.id ?? ""), title: String(a.title ?? ""), text: String(a.text ?? ""), color: String(a.color ?? ""), imageUrl: String(a.image_url ?? ""), thumbUrl: String(a.thumb_url ?? ""), fields: (a.fields as Record<string, string>[]) ?? [], actions: [] })),
    reactions: [],
    pinned: Boolean(api.pinned_to),
    edited: Boolean(api.edited),
    editedAt: (api.edited as Record<string, unknown>)?.ts as string ?? null,
    createdAt: new Date(Number(api.ts) * 1000).toISOString(),
    updatedAt: (api.edited as Record<string, unknown>)?.ts ? new Date(Number((api.edited as Record<string, unknown>).ts) * 1000).toISOString() : new Date(Number(api.ts) * 1000).toISOString(),
  }
}

export const SlackMessageManager = {
  async createMessage(channelId: string, text: string): Promise<SlackMessage> {
    const result = await SlackClient.post<Record<string, unknown>>("/chat.postMessage", { channel: channelId, text })
    if (result.success && result.data?.message) return mapApiMessage(result.data.message as Record<string, unknown>, channelId)
    const now = new Date().toISOString()
    return { id: "", channelId, userId: "", text, type: MessageType.STANDARD, threadId: null, mentions: [], attachments: [], reactions: [], pinned: false, edited: false, editedAt: null, createdAt: now, updatedAt: now }
  },

  async editMessage(channelId: string, ts: string, text: string): Promise<SlackMessage | null> {
    const result = await SlackClient.post<Record<string, unknown>>("/chat.update", { channel: channelId, ts, text })
    if (result.success && result.data?.message) return mapApiMessage(result.data.message as Record<string, unknown>, channelId)
    return null
  },

  async deleteMessage(channelId: string, ts: string): Promise<boolean> {
    const result = await SlackClient.post("/chat.delete", { channel: channelId, ts })
    return result.success
  },

  async pinMessage(channelId: string, ts: string): Promise<boolean> {
    const result = await SlackClient.post("/pins.add", { channel: channelId, timestamp: ts })
    return result.success
  },

  async retrieveMessage(channelId: string, ts: string): Promise<SlackMessage | null> {
    const result = await SlackClient.post<Record<string, unknown>>("/conversations.history", { channel: channelId, latest: ts, limit: 1, inclusive: true })
    if (result.success && result.data?.messages) {
      const msgs = result.data.messages as Record<string, unknown>[]
      if (msgs.length > 0) return mapApiMessage(msgs[0], channelId)
    }
    return null
  },

  async listMessages(channelId: string, limit: number = 100): Promise<SlackMessage[]> {
    const result = await SlackClient.post<Record<string, unknown>>("/conversations.history", { channel: channelId, limit })
    if (result.success && result.data?.messages) {
      return (result.data.messages as Record<string, unknown>[]).map((m) => mapApiMessage(m, channelId))
    }
    return []
  },

  async getMessage(id: string): Promise<SlackMessage | null> {
    const tsParts = id.split("-")
    return null
  },
}